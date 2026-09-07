"""向量存储客户端（#04 向量路，Milvus 单后端）。

后端：Milvus（生产唯一）。pymilvus 未安装 / Milvus 不可达时，向量召回降级为空，
主链路自动退回 BM25 单路兜底（见 hybrid.py）。

为什么选 Milvus：
  - 分布式 + HA（多节点 + 副本，原生网络访问，无本地文件痛点）；
  - HNSW + COSINE 索引，ms 级语义召回；
  - 多副本共享同一实例（K8s/云原生友好），支撑 AI 服务多副本部署；
  - 运维工具链成熟（Attu / Prometheus / Grafana exporter）。

设计要点：
  - 惰性初始化：首次访问才建连接 / 建 collection，不拖慢启动；
  - 失败即降级：任何异常都返回 [] / 0，不抛给主链路（BM25 单路兜底）；
  - 统一接口：对外暴露 upsert / query 语义，上层不感知 Milvus 细节。
"""

from __future__ import annotations

import logging
from typing import Any

from app.clients.embedding import embed, embed_one
from app.config import settings

logger = logging.getLogger(__name__)

# 全局后端实例 + 可用性标记
_backend: Any = None
_available: bool | None = None  # None=未探测；探测后缓存


# =============================================================================
# 后端适配器（鸭子类型：实现 upsert / query 两个方法）
# =============================================================================


class _MilvusBackend:
    """Milvus 后端（生产唯一）。

    用 pymilvus MilvusClient（2.4+）同步 API；调用处仍在 async 主链路里，
    与 db.py 的同步访问模式一致，不引入 async 驱动。
    Collection schema：id(varchar pk) / embedding(float_vector) / document(varchar) / metadata(json)
    索引：HNSW + COSINE，ms 级语义召回。
    """

    def __init__(self):
        from pymilvus import DataType, MilvusClient  # type: ignore

        self._MilvusClient = MilvusClient
        self._DataType = DataType
        self._client = MilvusClient(
            uri=settings.milvus_uri,
            token=settings.milvus_token or "",
            db_name=settings.milvus_database,
        )
        self._collection = settings.milvus_collection
        self._dim = settings.milvus_dim
        self._ensure_collection()
        logger.info(
            "[VectorStore] Milvus 就绪，uri=%s collection=%s dim=%d",
            settings.milvus_uri,
            self._collection,
            self._dim,
        )

    def _ensure_collection(self):
        """幂等：建 collection + HNSW 索引 + load。"""
        if self._client.has_collection(self._collection):
            self._client.load_collection(self._collection)
            return
        schema = self._MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", self._DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field("embedding", self._DataType.FLOAT_VECTOR, dim=self._dim)
        schema.add_field("document", self._DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata", self._DataType.JSON)
        index_params = self._MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 64},
        )
        self._client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )
        self._client.load_collection(self._collection)

    def upsert(self, ids: list[str], embeddings: list, documents: list[str], metadatas: list[dict]):
        """批量 upsert（按主键 id 覆盖）。"""
        data = [
            {
                "id": ids[i],
                "embedding": list(embeddings[i]),
                "document": documents[i],
                "metadata": metadatas[i],
            }
            for i in range(len(ids))
        ]
        self._client.upsert(collection_name=self._collection, data=data)

    def query(self, query_embeddings: list, n_results: int) -> dict:
        """向量近邻查询。返回统一 batch 结构 {ids:[[...]], metadatas:[[...]], distances:[[...]]}。

        Milvus COSINE metric 返回的 distance 实际是相似度 score（越大越相似），
        这里转成 cosine distance（1 - score），保持上层 sims = 1 - dist 的 round-trip 一致。
        """
        q = list(query_embeddings[0])
        res = self._client.search(
            collection_name=self._collection,
            data=[q],
            limit=n_results,
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            output_fields=["metadata"],
        )
        hits = res[0] if res else []
        ids = [str(h.get("id")) for h in hits]
        metadatas = [h.get("entity", {}).get("metadata") or {} for h in hits]
        distances = [1.0 - float(h.get("distance", 0.0)) for h in hits]
        return {"ids": [ids], "metadatas": [metadatas], "distances": [distances]}


# =============================================================================
# 工厂 + 可用性探测
# =============================================================================


def _check_available() -> bool:
    """探测后端依赖是否可用。结果缓存，缺失只告警一次。"""
    global _available
    if _available is None:
        try:
            import pymilvus  # noqa: F401

            _available = True
        except ImportError as exc:
            logger.warning(
                "[VectorStore] pymilvus 未安装，向量召回降级为 BM25 单路：%s",
                exc,
            )
            _available = False
    return _available


def _get_backend():
    """惰性获取后端实例。依赖缺失 / 初始化失败时抛 RuntimeError（上层降级）。"""
    global _backend
    if _backend is None:
        _backend = _MilvusBackend()
    return _backend


# =============================================================================
# 公共接口（upsert_coaches / search）—— 上层不感知后端差异
# =============================================================================


def upsert_coaches(coaches: list[dict[str, Any]]) -> int:
    """批量 upsert 教练向量（启动 / 教练更新时调用）。不可用时返回 0。"""
    if not coaches or not _check_available():
        return 0
    try:
        backend = _get_backend()
        texts = [
            f"{c.get('name', '')} {c.get('bio', '')} {c.get('city_name', '')}" for c in coaches
        ]
        vectors = embed(texts)
        if not vectors.size:
            return 0
        backend.upsert(
            ids=[f"coach_{c['coach_id']}" for c in coaches],
            embeddings=vectors.tolist(),
            documents=texts,
            metadatas=[{"coach_id": c["coach_id"]} for c in coaches],
        )
        logger.info("[VectorStore] upsert %d 教练向量（后端=milvus）", len(coaches))
        return len(coaches)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[VectorStore] upsert 失败，跳过：%s", exc)
        return 0


def search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """向量语义召回。返回 [(coach_id, similarity)]。不可用时返回 []。"""
    if not (query or "").strip() or not _check_available():
        return []
    try:
        backend = _get_backend()
        query_vec = embed_one(query)
        if not query_vec.size:
            return []
        result = backend.query(query_embeddings=[query_vec.tolist()], n_results=top_k)
        ids = [int(m["coach_id"]) for m in result["metadatas"][0]]
        # cosine distance → similarity = 1 - dist
        sims = [float(1 - d) for d in result["distances"][0]]
        return list(zip(ids, sims, strict=True))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[VectorStore] 召回失败，降级为空：%s", exc)
        return []


__all__ = ["search", "upsert_coaches"]
