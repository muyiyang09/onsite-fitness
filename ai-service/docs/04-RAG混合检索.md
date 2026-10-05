# AI 微服务开发文档 · #04 RAG 混合检索升级

> 版本：v1.0 · 2026-08-26
> **文档分类**：落地指南（Guideline） · **强制性**：建议遵循 · **用途**：指导把 Node2 从纯规则打分升级为多路召回 + 融合 + Rerank 的混合检索
> 前置阅读：[#02 §3 工具系统](./02-Agent工程能力地图.md#3-工具系统tools) · [#03 Loop 工程](./03-循环工程.md)
> 涉及文件：`app/clients/db.py` / `app/clients/embedding.py`（新增）/ `app/clients/vectorstore.py`（新增）/ `app/clients/bm25.py`（新增）/ `app/clients/reranker.py`（新增）/ `app/graphs/recommend_coach.py` / `app/config.py` / `pyproject.toml`

---

## 0. 文档说明

### 0.1 目标

把 `recommend_coach` 的 Node2（`retrieve_and_rank`）从「纯 SQL + 5 维规则打分」升级为「**三路召回 + RRF 融合 + Cross-Encoder Rerank**」的混合检索架构。

### 0.2 范围与边界

| 项 | 是否改动 | 说明 |
|---|---|---|
| 对外 HTTP 契约 | ❌ 不动 | 输入/输出 JSON 不变 |
| RecommendResult Schema | ❌ 不动 | 字段不变 |
| Node2 内部实现 | ✅ 重构 | 从规则打分 → 多路召回 + 融合 + Rerank |
| Node1 / Node3 实现 | ❌ 不动 | 沿用 #03 改造后的版本 |
| Loop 控制字段（retry_count / branch / relaxed_fields） | ✅ 保留 | 与 #03 兼容，向量库挂了仍能走规则兜底 |
| 数据库 | ✅ 已定 | Milvus 单后端（生产唯一），MySQL 无需迁移 |

---

## 1. 现状回顾

### 1.1 当前 Node2 实现

```
fetch_coaches(city_name)  → 全量捞 coach
fetch_courses()           → 全量捞 course
fetch_available_slots()   → 全量捞 schedule
       ↓
5 维加权打分（评分40% / 语义匹配35% / 等级10% / 距离10% / 档期5%）
       ↓
按 score_total 降序取 Top N
```

### 1.2 「语义匹配」维度的真相

[recommend_coach.py](../app/graphs/recommend_coach.py) 的 `_match_bio_score` 实际做法：

```python
def _match_bio_score(bio: str, keywords: list[str]) -> int:
    bio_l = (bio or "").lower()
    hits = [k for k in keywords if k.lower() in bio_l]  # ← 子串匹配，不是向量
    if not hits:
        return 40
    return min(100, 50 + 30 + min(20, (len(hits) - 1) * 10))
```

**这不是 RAG，是关键词子串匹配**。`_SPEC_SYNONYMS` 同义词扩展只是手动补丁，覆盖不了真实语义。

### 1.3 三大致命伤

| # | 问题 | 例子 | 后果 |
|---|---|---|---|
| 1 | **同义词丢失** | 用户「产后恢复」 vs 教练 bio「孕产康复经验丰富」 | 字面不命中 → score_match=40 → 排名靠后 |
| 2 | **词形变化丢失** | 「减脂」 vs 「脂肪减少」「体重管理」 | 召不出来 |
| 3 | **召回率上限低** | 教练总数 1000，但 city 过滤后剩 5 个 → 全部入榜 | Top N 等于全量，没有"筛选"意义 |

### 1.4 为什么不是「朴素向量 top-k」

朴素向量 top-k（单路 embedding 召回）在 2024 后已被淘汰，原因：

| 场景 | 单路向量的问题 |
|---|---|
| 用户「望京产后恢复」 | 「望京」是地名，向量相似度无意义，可能召回「国贸减脂」 |
| 用户「金牌教练」 | 「金牌」是等级词，应走 SQL 过滤，不应进向量 |
| 用户「预算 200」 | 数字应走 SQL 过滤，向量无法表达"≤200"语义 |
| 用户「男教练」 | 性别应走 SQL 过滤，向量无意义 |

**结论**：纯向量召回在结构化条件场景下精度反而比规则差。必须**结构化 SQL 硬过滤 + 关键词 BM25 + 语义向量三路并行**。

---

## 2. 设计思路：混合检索的范式

### 2.1 业界标准范式（2024~2026 主流）

```
                    ┌─ BM25 稀疏召回（关键词精确命中）
                    │   数据源：MySQL FULLTEXT / Elasticsearch
                    │   适用：「产后」「减脂」字面命中
                    │
Query ─────────────┼─ 向量稠密召回（语义相似）
                    │   数据源：pgvector / Milvus / Chroma
                    │   适用：「产后恢复」→「孕产康复经验丰富」
                    │
                    ├─ 结构化 SQL 过滤（硬条件）
                    │   数据源：MySQL
                    │   适用：city / level / sex / rating / price
                    │
                    └─ (可选) 交互式召回 ColBERT / SPLADE
                            ↓
                    RRF 融合（不依赖分数尺度）
                            ↓
                    Cross-Encoder Rerank 精排
                            ↓
                    Top K → LLM 生成理由
```

### 2.2 为什么这样设计而不是那样

| 决策点 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 召回路数 | 单路 / 双路 / 三路 | **三路** | 教练推荐三路各有不可替代的语义（结构化 / 字面 / 语义） |
| 融合算法 | RRF / 线性加权 / Convex | **RRF** | BM25 与向量分数尺度完全不同，RRF 只用 rank 不用 score，无需归一化 |
| Rerank | 用 / 不用 | **用**（可选开关） | 召回阶段用双塔模型（快），重排用 Cross-Encoder（准） |
| 向量库 | numpy / Chroma / pgvector / Milvus | **Milvus** | 分布式+HA，多副本共享同一实例；HNSW+COSINE ms 级召回；K8s/云原生友好 |
| Embedding 模型 | bge-m3 / bge-large-zh / OpenAI / m3e | **bge-m3** | 免费、中文好、单模型同时输出稠密+稀疏向量（一份模型干两路活） |
| Reranker | bge-reranker-v2-m3 / Cohere / jina | **bge-reranker-v2-m3** | 免费、中文好、本地部署 |
| 兜底策略 | 全切规则 / 全切向量 | **混合分**：α·规则 + β·向量 + γ·BM25 | 任一路挂了仍能跑（#03 兼容） |

### 2.3 关键认知

**召回 ≠ 排序**，这是 RAG 工程的核心区分：

| 阶段 | 目标 | 模型类型 | 数量 |
|---|---|---|---|
| 召回（Retrieval） | 高 recall，捞尽量多相关候选 | 双塔模型（query/doc 独立 embedding） | Top 50~100 |
| 重排（Rerank） | 高 precision，精排最相关的 | Cross-Encoder（query+doc 拼一起过模型） | Top 3~5 |

**别用 Cross-Encoder 做召回**——慢 100 倍；**别用双塔做排序**——精度差。各司其职。

---

## 3. 落地方案

### 3.1 整体架构

```
                 ┌──────────────────────────────────────────┐
                 │        retrieve_and_rank 节点            │
                 │  （#03 的 Loop 控制字段保留：retry_count, │
                 │   branch, relaxed_fields, ...）          │
                 └──────────────────────────────────────────┘
                                  │
                                  ▼
            ┌─────────────────────────────────────────┐
            │  Stage 1: 结构化 SQL 硬过滤（必走）     │
            │  city / level / sex / rating / 预算     │
            │  输出：filtered_coaches（≤200 条）     │
            └─────────────────────────────────────────┘
                                  │
            ┌─────────────────────┴─────────────────────┐
            ▼                                           ▼
   ┌────────────────────┐                    ┌────────────────────┐
   │ Stage 2a: BM25 召回│                    │ Stage 2b: 向量召回  │
   │ (filtered 内)       │                    │ (filtered 内)       │
   │ MySQL FULLTEXT      │                    │ Milvus              │
   │ 输出：top 50 + rank │                    │ 输出：top 50 + rank │
   └────────────────────┘                    └────────────────────┘
                                  │
                                  ▼
            ┌─────────────────────────────────────────┐
            │  Stage 3: RRF 融合（k=60）              │
            │  score = 1/(60+rank_bm25) + 1/(60+rank_vec)│
            │  输出：top 30 融合排序                   │
            └─────────────────────────────────────────┘
                                  │
                                  ▼ (可选开关)
            ┌─────────────────────────────────────────┐
            │  Stage 4: Cross-Encoder Rerank         │
            │  bge-reranker-v2-m3                     │
            │  输出：top N（默认 3）精排              │
            └─────────────────────────────────────────┘
                                  │
                                  ▼
            ┌─────────────────────────────────────────┐
            │  Stage 5: 与规则分兜底融合              │
            │  final = α·规则分(0~100) + β·rerank_score│
            │  α=0.3, β=0.7（rerank 启用时）          │
            │  α=1.0, β=0.0（rerank 关闭时）          │
            └─────────────────────────────────────────┘
                                  │
                                  ▼
                          候选 Top N + branch 路由
                          （交给 #03 的 ConditionalRouter）
```

### 3.2 Stage 1：结构化 SQL 硬过滤

**保留现有逻辑**，仅做小重构——把"硬过滤"从"打分"里拆出来，独立成一个函数：

```python
# app/graphs/recommend_coach.py 改造


def _hard_filter(coaches: list[dict], intent: dict) -> list[dict]:
    """结构化硬过滤：city / level / sex / rating。返回过滤后的教练列表。"""
    city_name = intent.get("city_name")
    min_level = intent.get("level")
    min_rating = intent.get("min_rating")
    male_only = intent.get("male_only")

    filtered = []
    for c in coaches:
        if city_name and c.get("city_name") != city_name:
            continue
        if min_level is not None and int(c.get("level", 0)) < int(min_level):
            continue
        if min_rating is not None and float(c.get("rating", 0)) < float(min_rating):
            continue
        if male_only is True and c.get("sex") != "1":
            continue
        if male_only is False and c.get("sex") != "0":
            continue
        filtered.append(c)
    return filtered
```

**与 #03 兼容**：当 `filtered` 为空时，仍走 #03 的 `branch: "relax"` 回 Node1 放宽条件——混合检索不替代 Loop 工程，而是与之协作。

### 3.3 Stage 2a：BM25 召回

#### 3.3.1 数据源选型

| 方案 | 优点 | 缺点 | 适用 |
|---|---|---|---|
| **MySQL 8.0 ngram FULLTEXT** | 复用现有库，零新增组件 | 中文分词粗糙，召回质量中等 | 数据量 < 10 万 |
| Elasticsearch | 业界标杆，召回质量高 | 引入独立服务，运维成本 | 数据量大或专业搜索 |
| **rank_bm25（Python 库）** | 零依赖，进程内计算 | 全量内存，启动慢 | 数据量 < 1 万（本项目首选） |

**本项目推荐：rank_bm25** —— 教练数据量小（几百~几千），全量加载内存做 BM25 完全够用，零运维成本。

#### 3.3.2 代码骨架

```python
# app/clients/bm25.py（新增）
"""BM25 稀疏召回：基于 rank_bm25 库的进程内实现。
教练 bio 量小（<1 万），全量加载内存。
启动时构建索引（惰性首次调用），教练更新时增量重建。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import jieba  # 中文分词
from rank_bm25 import BM25Okapi

from app.clients.db import fetch_all

logger = logging.getLogger(__name__)

_index: Optional[_BM25Index] = None


class _BM25Index:
    """BM25 索引：coach_id 列表 + BM25 实例。"""

    def __init__(self, coaches: list[dict[str, Any]]):
        self.coach_ids: list[int] = [int(c["coach_id"]) for c in coaches]
        # 关键：把 bio + name + city_name 拼起来分词，召回更准
        self.corpus: list[list[str]] = [
            list(jieba.cut(f"{c.get('name', '')} {c.get('bio', '')} {c.get('city_name', '')}"))
            for c in coaches
        ]
        self.bm25 = BM25Okapi(self.corpus)
        self.coaches = coaches  # 保留原数据，rerank 阶段用

    def search(self, query: str, top_k: int = 50) -> list[tuple[int, float]]:
        """返回 [(coach_id, bm25_score)]，按分数降序。"""
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(zip(self.coach_ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


def get_index() -> _BM25Index:
    """惰性构建/获取全局 BM25 索引。"""
    global _index
    if _index is None:
        coaches = _fetch_all_coaches_for_index()
        _index = _BM25Index(coaches)
        logger.info("[BM25] 索引构建完成，coach 数=%d", len(coaches))
    return _index


def _fetch_all_coaches_for_index() -> list[dict[str, Any]]:
    """从 MySQL 取所有正常教练用于构建索引。失败时返回空列表（上层走兜底）。"""
    try:
        rows = fetch_all("SELECT id, name, bio, city_name FROM coach WHERE status = 1")
        return [{"coach_id": r["id"], **r} for r in rows]
    except Exception as exc:
        logger.warning("[BM25] 索引构建失败，将走规则兜底：%s", exc)
        return []


def search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """对外暴露的 BM25 召回接口。索引不可用时返回空列表。"""
    if not query.strip():
        return []
    try:
        return get_index().search(query, top_k)
    except Exception as exc:
        logger.warning("[BM25] 召回失败：%s", exc)
        return []


def rebuild_index() -> int:
    """强制重建索引（教练数据变更时调用）。返回索引的教练数。"""
    global _index
    _index = None
    return len(get_index().coach_ids)
```

### 3.4 Stage 2b：向量召回

#### 3.4.1 Embedding 模型选型

| 模型 | 大小 | 中文 | 多语言 | 稀疏向量 | 推荐场景 |
|---|---|---|---|---|---|
| **bge-m3** | 2.3GB | ✅ 优秀 | ✅ 100+ | ✅ 同时输出 | **本项目首选** |
| bge-large-zh-v1.5 | 1.3GB | ✅ 优秀 | ❌ | ❌ | 纯中文 |
| m3e-base | 0.4GB | ✅ 良好 | ❌ | ❌ | 资源紧张 |
| OpenAI text-embedding-3-large | API | ✅ | ✅ | ❌ | 不在乎数据出境 + 付费 |
| Cohere embed-multilingual-v3 | API | ✅ | ✅ | ❌ | 付费 |

**选 bge-m3 的关键理由**：单模型同时输出**稠密向量 + 稀疏向量 + 多向量**，一份模型干 BM25 + 向量两路活，简化部署。

#### 3.4.2 向量库选型

| 方案 | 部署 | 持久化 | 多副本 | 适用数据量 | 推荐 |
|---|---|---|---|---|---|
| **numpy + 内存** | 进程内 | ❌ | ❌ | < 1 万 | 起步阶段 |
| **Chroma** | 嵌入式 | ✅ 文件 | ❌ | < 100 万 | 嵌入式首选 |
| **pgvector** | PostgreSQL 扩展 | ✅ | ✅ | < 1000 万 | 已有 PG 时 |
| **Milvus** | 独立服务 | ✅ | ✅ | > 1000 万 | **本项目首选** |
| **Faiss** | 进程内 | ⚠️ | ❌ | 任意 | 性能极致 |

**本项目选 Milvus** —— 分布式+HA（多节点副本，原生网络访问，无本地文件痛点）；HNSW+COSINE ms 级召回；多副本共享同一实例（K8s/云原生友好）；运维工具链成熟（Attu/Prometheus/Grafana）。

#### 3.4.3 代码骨架

```python
# app/clients/embedding.py（新增）
"""Embedding 客户端：基于 sentence-transformers 加载 bge-m3。
支持本地模型 + LiteLLM 远程模型两种模式。
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    """惰性加载本地 embedding 模型（首次调用约 5s）。"""
    global _model
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore

        _model = BGEM3FlagModel(
            settings.embedding_model,
            use_fp16=settings.embedding_use_fp16,
            device=settings.embedding_device,
        )
        logger.info(
            "[Embedding] 模型加载完成：%s @ %s", settings.embedding_model, settings.embedding_device
        )
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """批量 embedding，返回 [N, dim] 的 numpy 数组。"""
    if not texts:
        return np.array([])
    model = _get_model()
    result = model.encode(texts, batch_size=32, max_length=512)["dense_vecs"]
    return np.array(result)


def embed_one(text: str) -> np.ndarray:
    """单条 embedding，返回 [dim] 的 numpy 数组。"""
    return embed([text])[0]
```

```python
# app/clients/vectorstore.py（新增）
"""向量存储：基于 pymilvus MilvusClient 的分布式向量库（生产唯一后端）。
启动时惰性建集合 + HNSW 索引，支持多副本共享同一实例。
pymilvus 未装 / Milvus 不可达 → 向量召回返回空，主链路退回 BM25 单路。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.clients.embedding import embed, embed_one
from app.config import settings

logger = logging.getLogger(__name__)

_client = None
_collection_ready = False


def _get_client():
    """惰性获取 MilvusClient（pymilvus 2.4+）。"""
    global _client
    if _client is None:
        from pymilvus import MilvusClient  # type: ignore

        _client = MilvusClient(
            uri=settings.milvus_uri,
            token=settings.milvus_token,
            db_name=settings.milvus_database,
        )
        logger.info(
            "[VectorStore] Milvus 客户端就绪，uri=%s db=%s",
            settings.milvus_uri,
            settings.milvus_database,
        )
    return _client


def _ensure_collection():
    """惰性创建集合（schema: id/embedding/document/metadata + HNSW COSINE 索引）。"""
    global _collection_ready
    if _collection_ready:
        return
    from pymilvus import DataType  # type: ignore

    client = _get_client()
    name = settings.milvus_collection

    if not client.has_collection(name):
        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=settings.milvus_dim)
        schema.add_field("document", DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata", DataType.JSON)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="HNSW",
            metric_type="COSINE",
            params={"M": 16, "efConstruction": 64},
        )
        client.create_collection(name, schema=schema, index_params=index_params)
        logger.info("[VectorStore] Milvus 集合已创建，name=%s dim=%d", name, settings.milvus_dim)

    client.load_collection(name)
    _collection_ready = True


def upsert_coaches(coaches: list[dict[str, Any]]) -> int:
    """批量 upsert 教练向量（启动时 / 教练更新时调用）。"""
    if not coaches:
        return 0
    _ensure_collection()
    client = _get_client()
    texts = [f"{c.get('name', '')} {c.get('bio', '')} {c.get('city_name', '')}" for c in coaches]
    vectors = embed(texts)
    client.upsert(
        collection_name=settings.milvus_collection,
        data=[
            {
                "id": f"coach_{c['coach_id']}",
                "embedding": vectors[i].tolist(),
                "document": texts[i],
                "metadata": {"coach_id": c["coach_id"]},
            }
            for i, c in enumerate(coaches)
        ],
    )
    logger.info("[VectorStore] upsert %d 教练向量", len(coaches))
    return len(coaches)


def search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """向量召回。返回 [(coach_id, similarity)]。
    pymilvus 未装 / Milvus 不可达 → 返回空，主链路退回 BM25 单路。
    """
    if not query.strip():
        return []
    try:
        _ensure_collection()
        client = _get_client()
        query_vec = embed_one(query).tolist()
        result = client.search(
            collection_name=settings.milvus_collection,
            data=[query_vec],
            limit=top_k,
            output_fields=["metadata"],
            search_params={"params": {"ef": 64}},
        )
        hits = result[0]  # COSINE metric 下 distance 即相似度（越大越相似）
        return [
            (int(hit["entity"]["metadata"]["coach_id"]), float(hit["distance"])) for hit in hits
        ]
    except Exception as exc:
        logger.warning("[VectorStore] 召回失败（向量召回返回空，主链路退回 BM25 单路）：%s", exc)
        return []


def rebuild(coaches: list[dict[str, Any]]) -> int:
    """全量重建（drop 旧集合 + 重建 schema + upsert 新）。"""
    global _collection_ready
    try:
        client = _get_client()
        if client.has_collection(settings.milvus_collection):
            client.drop_collection(settings.milvus_collection)
    except Exception:
        pass
    _collection_ready = False
    _ensure_collection()
    return upsert_coaches(coaches)
```

### 3.5 Stage 3：RRF 融合

#### 3.5.1 算法

**RRF (Reciprocal Rank Fusion)** 公式：

```
score(doc) = Σ_i  1 / (k + rank_i(doc))
```

- `i` 遍历所有召回路（BM25 / 向量 / ...）
- `rank_i(doc)` 是 doc 在第 i 路结果中的排名（从 1 开始）
- `k` 通常取 60，平滑常数（避免 rank=1 的 doc 主导）

**为什么用 RRF 不用线性加权**：
- BM25 分数范围 0~30+，向量相似度 0~1，尺度完全不同
- 线性加权要先归一化，归一化策略（min-max / z-score）本身是另一个超参
- RRF 只用 rank 不用 score，跨尺度天然兼容

#### 3.5.2 代码骨架

```python
# app/graphs/recommend_coach.py 新增

RRF_K = 60  # 业界经验值


def _rrf_fuse(
    bm25_results: list[tuple[int, float]],
    vec_results: list[tuple[int, float]],
    top_k: int = 30,
) -> list[tuple[int, float]]:
    """RRF 融合 BM25 + 向量两路召回结果。
    返回 [(coach_id, rrf_score)]，按 rrf_score 降序。
    """
    scores: dict[int, float] = {}

    for rank, (coach_id, _) in enumerate(bm25_results, 1):
        scores[coach_id] = scores.get(coach_id, 0) + 1.0 / (RRF_K + rank)

    for rank, (coach_id, _) in enumerate(vec_results, 1):
        scores[coach_id] = scores.get(coach_id, 0) + 1.0 / (RRF_K + rank)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]
```

### 3.6 Stage 4：Cross-Encoder Rerank（可选）

#### 3.6.1 为什么可选

Cross-Encoder 比 dual-encoder 准但慢 100 倍，所以：
- **数据量小**（< 100 候选）→ 跑得起 → 开启
- **数据量大** → 关闭，靠 RRF 排序够了
- **质量要求高**（如 VIP 客户） → 开启

本项目教练数小，建议**默认开启**，但保留开关。

#### 3.6.2 代码骨架

```python
# app/clients/reranker.py（新增）
"""Rerank 客户端：基于 bge-reranker-v2-m3 的 Cross-Encoder 重排。
Cross-Encoder 把 (query, doc) 拼一起过模型，输出相关性分数。
比 dual-encoder 准但慢，仅用于 top 30 → top N 的精排。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from FlagEmbedding import FlagReranker  # type: ignore

        _model = FlagReranker(
            settings.reranker_model,
            use_fp16=settings.reranker_use_fp16,
            device=settings.reranker_device,
        )
    return _model


def rerank(query: str, docs: list[dict[str, Any]], top_n: int = 3) -> list[dict[str, Any]]:
    """对 docs 按 query 相关性重排，返回 top N。
    docs: [{"coach_id": 1, "text": "李教练 专注减脂 8 年", ...}, ...]
    """
    if not query.strip() or not docs:
        return docs[:top_n]
    try:
        model = _get_model()
        pairs = [[query, d.get("text", "")] for d in docs]
        scores = model.compute_score(pairs, normalize=True)
        if isinstance(scores, float):  # 单条输入返回标量
            scores = [scores]
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]
    except Exception as exc:
        logger.warning("[Reranker] 重排失败，跳过：%s", exc)
        return docs[:top_n]
```

### 3.7 Stage 5：与规则分兜底融合

**关键设计**：保留 #03 改造后的 `_distance_score / _schedule_ratio / _match_bio_score` 等规则分作为兜底，与混合检索分线性加权：

```python
# app/graphs/recommend_coach.py 改造 retrieve_and_rank


def retrieve_and_rank(state: RecommendState) -> dict[str, Any]:
    intent = state.get("intent") or {}
    top_n = int(state.get("top_n") or 3)

    # ---- Stage 1: 硬过滤（保留 #03 逻辑）----
    coaches = _fetch_coaches(intent.get("city_name"))
    courses = _fetch_courses()
    slots = _fetch_available_slots([c["coach_id"] for c in coaches])
    filtered = _hard_filter(coaches, intent)

    # 候选为空 → 走 #03 的 relax 路由（不变）
    if not filtered:
        return _handle_empty_candidates(state, intent)

    # ---- Stage 2a + 2b: BM25 + 向量召回（并行，filtered 内）----
    user_query = state.get("user_query", "")
    bm25_results = bm25_search(user_query, top_k=50)
    vec_results = vector_search(user_query, top_k=50)

    # 仅保留 filtered 内的（intersection）
    filtered_ids = {c["coach_id"] for c in filtered}
    bm25_results = [(cid, s) for cid, s in bm25_results if cid in filtered_ids]
    vec_results = [(cid, s) for cid, s in vec_results if cid in filtered_ids]

    # ---- Stage 3: RRF 融合 ----
    fused = _rrf_fuse(bm25_results, vec_results, top_k=30)
    # 也加入 filtered 中但不在召回结果里的（兜底，避免遗漏）
    recalled_ids = {cid for cid, _ in fused}
    for c in filtered:
        if c["coach_id"] not in recalled_ids:
            fused.append((c["coach_id"], 0.0))  # 最低分兜底

    # 取前 30 进入 rerank
    top_for_rerank = fused[:30]
    coach_map = {c["coach_id"]: c for c in filtered}
    docs_for_rerank = [
        {
            "coach_id": cid,
            "text": _build_doc_text(coach_map[cid], user_query),
            "coach": coach_map[cid],
            "rrf_score": score,
        }
        for cid, score in top_for_rerank
        if cid in coach_map
    ]

    # ---- Stage 4: Rerank（可选）----
    if settings.reranker_enabled and docs_for_rerank:
        reranked = reranker.rerank(user_query, docs_for_rerank, top_n=10)
    else:
        reranked = docs_for_rerank[:10]

    # ---- Stage 5: 与规则分融合 ----
    candidates = []
    keywords = _expand_keywords(
        intent.get("specialization"), intent.get("specialization_tags") or []
    )
    matched_course, over_budget = _apply_budget(
        _match_course(
            intent.get("specialization"), intent.get("specialization_tags") or [], courses
        ),
        intent.get("max_price"),
        courses,
    )
    bucket = _time_bucket(intent.get("time_slot"))

    for item in reranked[:top_n]:
        c = item["coach"]
        rerank_score = float(item.get("rerank_score", item["rrf_score"]))

        # 规则分（保留 #03 的 5 维，作兜底）
        score_rating = int(float(c.get("rating") or 0) / 5.0 * 100)
        score_level = int(int(c.get("level") or 1) / 4.0 * 100)
        score_match = _match_bio_score(c.get("bio") or "", keywords)
        score_distance = _distance_score(c.get("service_radius_km") or 0)
        score_schedule = _compute_schedule_score(slots, c["coach_id"], bucket)

        rule_total = (
            score_rating * _WEIGHTS["rating"]
            + score_match * _WEIGHTS["match"]
            + score_level * _WEIGHTS["level"]
            + score_distance * _WEIGHTS["distance"]
            + score_schedule * _WEIGHTS["schedule"]
        )
        # rerank_score 范围 0~1，归一到 0~100
        rerank_norm = rerank_score * 100

        # 最终分：α·规则 + β·rerank
        alpha = settings.rule_weight  # 默认 0.3
        beta = 1.0 - alpha  # 默认 0.7
        final = alpha * rule_total + beta * rerank_norm

        candidates.append(
            CoachCandidate(
                coach_id=int(c["coach_id"]),
                name=c.get("name", ""),
                level=int(c.get("level") or 1),
                rating=float(c.get("rating") or 0),
                service_radius_km=float(c.get("service_radius_km") or 0),
                city_name=c.get("city_name") or "",
                bio=c.get("bio") or "",
                specialization=matched_course.get("category") if matched_course else None,
                course_name=matched_course.get("name") if matched_course else None,
                price=float(matched_course["price"]) if matched_course else 0.0,
                distance_km_est=None,
                schedule_match_ratio=round(_schedule_ratio_safe(slots, c["coach_id"], bucket), 2),
                score_rating=score_rating,
                score_level=score_level,
                score_match=score_match,
                score_distance=score_distance,
                score_schedule=score_schedule,
                score_total=round(final, 2),
            )
        )

    # 候选为空兜底（rerank 失败 / 召回失败）
    if not candidates:
        return _handle_empty_candidates(state, intent)

    candidates.sort(key=lambda x: x.score_total, reverse=True)
    top = candidates[:top_n]
    return {
        "candidates": [c.model_dump() for c in top],
        "matched_course": matched_course,
        "over_budget": over_budget,
        "branch": "to_reason",  # 保留 #03 路由
    }
```

---

## 4. 数据预计算与增量更新

### 4.1 启动时预构建索引

```python
# app/main.py lifespan 钩子新增
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI 服务启动...")

    # 预构建 BM25 + 向量索引（异步，不阻塞启动）
    if settings.hybrid_retrieval_enabled:
        from app.clients.db import fetch_all
        from app.clients.bm25 import get_index as get_bm25_index
        from app.clients.vectorstore import upsert_coaches

        try:
            rows = fetch_all(
                "SELECT id, name, bio, city_name, sex, level, rating, "
                "service_radius_km, city_code FROM coach WHERE status = 1"
            )
            coaches = [{"coach_id": r["id"], **r} for r in rows]
            get_bm25_index()  # 触发构建
            if not settings.vector_skip_initial_upsert:
                upsert_coaches(coaches)
            logger.info("混合检索索引就绪，coach 数=%d", len(coaches))
        except Exception as exc:
            logger.warning("索引构建失败，混合检索将走规则兜底：%s", exc)

    yield
    logger.info("🛑 AI 服务停止")
```

### 4.2 教练数据变更增量更新

教练更新时（管理端审核通过 / 教练修改资料），通过 HTTP 钩子触发增量更新：

```python
# app/main.py 新增
@app.post("/internal/reindex", tags=["Internal"])
def reindex(coach_ids: list[int] = Body([])):
    """管理端审核通过教练后调此接口增量更新索引。"""
    from app.clients.bm25 import rebuild_index
    from app.clients.vectorstore import upsert_coaches
    from app.clients.db import fetch_all

    if not coach_ids:
        # 全量重建
        rebuild_index()
        rows = fetch_all("SELECT id, name, bio, city_name FROM coach WHERE status = 1")
        upsert_coaches([{"coach_id": r["id"], **r} for r in rows])
        return {"rebuilt": "all"}

    # 增量：仅更新指定 coach_ids
    placeholders = ",".join(str(i) for i in coach_ids)
    rows = fetch_all(
        f"SELECT id, name, bio, city_name FROM coach WHERE id IN ({placeholders}) AND status = 1"
    )
    upsert_coaches([{"coach_id": r["id"], **r} for r in rows])
    rebuild_index()  # BM25 全量重建（数据量小，无需增量）
    return {"updated": len(rows)}
```

### 4.3 后台定时全量重建（兜底）

每小时跑一次全量重建，防止漏更新：

```python
# app/main.py lifespan 钩子内启动后台任务
import asyncio


async def _periodic_rebuild():
    while True:
        await asyncio.sleep(3600)
        try:
            # 触发全量重建
            ...
        except Exception as exc:
            logger.warning("定时全量重建失败：%s", exc)
```

---

## 5. 配置项

### 5.1 config.py 新增字段

```python
# app/config.py 新增

# —— 混合检索总开关 ——
hybrid_retrieval_enabled: bool = Field(
    default=False,
    description="是否启用混合检索（默认关，二期灰度开）",
)

# —— Embedding ——
embedding_model: str = Field(
    default="BAAI/bge-m3",
    description="HuggingFace 模型名",
)
embedding_device: str = Field(
    default="cpu",
    description="cpu / cuda / mps",
)
embedding_use_fp16: bool = Field(default=True)

# —— 向量库（Milvus 单后端）——
milvus_uri: str = Field(
    default="http://127.0.0.1:19530",
    description="Milvus 连接地址（生产唯一向量库）",
)
milvus_token: str = Field(
    default="",
    description="Milvus 鉴权 token（无鉴权留空）",
)
milvus_database: str = Field(
    default="default",
    description="Milvus database 名",
)
milvus_collection: str = Field(
    default="ai_vector_coach",
    description="Milvus collection 名",
)
milvus_dim: int = Field(
    default=1024,
    description="向量维度（与 bge-m3 dense 1024 对齐）",
)
vector_skip_initial_upsert: bool = Field(
    default=False,
    description="启动时是否跳过 upsert（已存在索引时 True 加速启动）",
)

# —— Reranker ——
reranker_enabled: bool = Field(default=True)
reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3")
reranker_device: str = Field(default="cpu")
reranker_use_fp16: bool = Field(default=True)

# —— 融合权重 ——
rule_weight: float = Field(
    default=0.3,
    ge=0.0,
    le=1.0,
    description="规则分权重 α；rerank 分权重 = 1 - α",
)
rrf_k: int = Field(default=60, description="RRF 平滑常数")
```

### 5.2 .env.example 新增

```bash
# ===== 混合检索 =====
HYBRID_RETRIEVAL_ENABLED=false      # 二期灰度开启
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cpu
EMBEDDING_USE_FP16=true
MILVUS_URI=http://127.0.0.1:19530
MILVUS_TOKEN=
MILVUS_DATABASE=default
MILVUS_COLLECTION=ai_vector_coach
MILVUS_DIM=1024
VECTOR_SKIP_INITIAL_UPSERT=false
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_DEVICE=cpu
RERANKER_USE_FP16=true
RULE_WEIGHT=0.3
RRF_K=60
```

### 5.3 pyproject.toml 新增依赖

```toml
dependencies = [
    # ... 原依赖 ...
    "rank-bm25==0.2.2",            # BM25 实现
    "jieba==0.42.1",               # 中文分词
    "pymilvus>=2.4.0",            # 向量库（Milvus 单后端）
    "FlagEmbedding==1.3.4",        # bge-m3 + bge-reranker
    "numpy>=1.26,<2.0",            # 向量计算
]
```

---

## 6. 落地步骤

| 步骤 | 文件 | 改动 | 说明 |
|---|---|---|---|
| 1 | `pyproject.toml` | 加 5 个依赖 | rank-bm25 / jieba / pymilvus / FlagEmbedding / numpy |
| 2 | `app/config.py` | 加 11 个字段 | 见 §5.1 |
| 3 | `.env.example` | 加 11 个环境变量 | 见 §5.2 |
| 4 | `app/clients/bm25.py` | 新建 | 见 §3.3.2 |
| 5 | `app/clients/embedding.py` | 新建 | 见 §3.4.3 |
| 6 | `app/clients/vectorstore.py` | 新建 | 见 §3.4.3 |
| 7 | `app/clients/reranker.py` | 新建 | 见 §3.6.2 |
| 8 | `app/graphs/recommend_coach.py` | 改 `retrieve_and_rank` 节点 + 加 `_rrf_fuse` | 见 §3.5.2 / §3.7 |
| 9 | `app/main.py` | 加 lifespan 索引预构建 + `/internal/reindex` 端点 | 见 §4 |
| 10 | `tests/test_recommend.py` | 加 3 个混合检索 case | 见 §7 |

---

## 7. 验收标准

### 7.1 功能验收

| Case | 输入 | 期望 |
|---|---|---|
| **C1 同义词召回** | query="产后恢复"，bio 含"孕产康复" | 向量召回命中（旧规则只给 40 分） |
| **C2 关键词精确命中** | query="减脂"，bio 含"减脂" | BM25 召回 top1，向量召回 top1（双路命中） |
| **C3 结构化过滤生效** | city="北京市"，level=4 | 仅金牌北京教练入榜（向量不能越界） |
| **C4 兜底** | 关掉 Milvus + Reranker | 走规则分，仍能返回结果（与 #03 行为一致） |
| **C5 性能** | 1000 条教练 | 单次混合检索 < 500ms（含 Rerank） |

### 7.2 与 #03 兼容性验收

- `branch` / `retry_count` / `relaxed_fields` 字段流向不变
- 候选为空时仍走 `relax` 回 Node1
- `over_budget` / `used_mock` 语义不变
- 原 4 条 smoke test case 全过

### 7.3 可观测验收

- 日志含 `[BM25] 召回 N 条` / `[VectorStore] 召回 N 条` / `[Reranker] 重排 N→N` 三类标记
- Trace 中能看到三路召回的耗时分布

---

## 8. 关键设计决策回顾

| 决策点 | 选项 | 选择 | 理由 |
|---|---|---|---|
| 召回路数 | 单路 / 双路 / 三路 | 三路 | 教练推荐三路各有不可替代语义 |
| 融合算法 | RRF / 线性加权 / Convex | RRF | 不依赖分数尺度，跨路天然兼容 |
| BM25 数据源 | MySQL FULLTEXT / rank_bm25 / ES | rank_bm25 | 数据量小，零运维 |
| 向量库 | numpy / Chroma / pgvector / Milvus | Milvus | 分布式+HA、多副本共享、HNSW+COSINE ms 级召回 |
| Embedding | bge-m3 / bge-large-zh / OpenAI | bge-m3 | 免费、中文好、单模型多向量 |
| Reranker | bge-reranker-v2-m3 / Cohere / jina | bge-reranker-v2-m3 | 免费、中文好、本地部署 |
| Rerank 启用 | 默认开 / 默认关 | 默认开（数据量小） | 数据量小跑得起 |
| 与规则分融合 | 替换 / 加权 | 加权（α·规则 + β·rerank） | 任一路挂了仍能跑 |
| 全量 vs 增量更新 | 全量 / 增量 / 混合 | 混合（增量 + 定时全量兜底） | 防漏更新 |

---

## 9. 后续衔接

| 后续文档 | 与 #04 的关系 |
|---|---|
| #05 商业化加固 | 把 BM25 + 向量召回改为异步（`bm25.async_search` / `vectorstore.async_search`） |
| #06 Harness 工程 | Eval 集新增"召回质量"metric（Recall@K / nDCG@K） |
| #07 MCP 工具层 | `bm25.search` / `vectorstore.search` / `reranker.rerank` 抽象为 MCP tool，跨 Agent 复用 |
| #08 双 Agent 落地 | 评价摘要 Agent 复用本套混合检索召回相关历史评价 |

---

## 10. 学习要点小结

读完这份文档，你应该掌握：

1. **召回 ≠ 排序**：召回追求高 recall 用双塔模型（快），重排追求高 precision 用 Cross-Encoder（准），各司其职
2. **三路并行各有不可替代语义**：结构化 SQL（硬条件）/ BM25（字面命中）/ 向量（语义相似），不要互相替代
3. **RRF 是跨尺度融合的银弹**：当多路召回分数尺度不同时（BM25 vs 向量相似度），用 rank 不用 score
4. **Embedding + Rerank 用同源模型族**：bge-m3 + bge-reranker 同出 BAAI，对齐训练数据，效果更好
5. **保留规则分作兜底**：混合检索是"加强"不是"替代"，向量库挂了仍能跑（与 #03 Loop 工程兼容）
6. **本项目统一选 Milvus**：分布式+HA，多副本共享同一实例，数据量小也无需切嵌入式库；选型科普对比见 §3.4.2
7. **增量 + 定时全量双保险**：增量保证实时，定时全量兜底防漏

回复「开始 #05」推进商业化加固，或就 #04 某节展开讨论。
