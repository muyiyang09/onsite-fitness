"""混合检索编排层（#04 RAG 升级的核心）。

把「BM25 稀疏召回 + 向量稠密召回 + RRF 融合 + 可选 Cross-Encoder 重排」编排成一个
对上层友好的单一接口 `hybrid_match_scores()`，返回 `{coach_id: 0~1 相关度}`。

================================================================================
关键设计决策（为什么这样设计，而不是照搬文档的 Stage 5 最终融合）
================================================================================

文档 #04 的 Stage 5 建议 `final = α·规则总分 + β·rerank 分`（全局线性融合）。
这里做了一个**有意的、可解释的偏离**：把混合相关度**折进 score_match（语义匹配维）**，
而不是新增一个全局融合项。理由：

  1. 语义匹配维度本来就有 35% 权重，而 #04 的初衷就是「把 score_match 从子串匹配
     升级成真正的语义匹配」。折进 score_match 是「在正确的位置升级」，不是另起炉灶。
  2. 保留 5 维权重预算（评分40/匹配35/等级10/距离10/档期5）不变，不引入新的 α/β 超参，
     评分体系仍然可读、可解释。
  3. 向后兼容：hybrid 关闭 / BM25 空结果 / 依赖缺失时，score_match 退回原 `_match_bio_score`
     子串匹配，行为与 #03 完全一致——这是「加强」不是「替代」。

================================================================================
轻量降级策略（当前国内环境）
================================================================================

  - BM25（jieba + rank_bm25）：纯 Python，离线可跑，**默认启用**。
  - 向量召回（bge-m3 + milvus）：重依赖未装，`vectorstore.search()` 恒返回 []，
    于是自动走「单路 BM25」分支（min-max 归一化）。
  - 重排（bge-reranker）：默认关 + 依赖缺失降级 no-op。
  三者缺谁都能跑，只是召回路数从 3 → 2 → 1 逐级退化，永不抛异常打断推荐主链路。
"""

from __future__ import annotations

import logging
from typing import Any

from app.clients import bm25, reranker, vectorstore
from app.config import settings

logger = logging.getLogger(__name__)


def _coach_text(c: dict[str, Any]) -> str:
    """拼接教练可检索文本（与 BM25 索引 / 向量 upsert 保持一致）。"""
    return f"{c.get('name', '')} {c.get('bio', '')} {c.get('city_name', '')}"


def _rrf_fuse(
    ranked_lists: list[list[tuple[int, float]]],
    k: int = 60,
    top_k: int = 30,
) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion：只用排名不用分数，跨尺度融合多路召回。

    为什么用 RRF 而不是线性加权：BM25 分数（0~几十）与向量相似度（0~1）尺度完全不同，
    线性加权要先归一化（而归一化策略本身又是一个超参）；RRF 只用 rank，天然跨尺度兼容。
    公式：score(doc) = Σ_i 1/(k + rank_i(doc))。
    """
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, (coach_id, _) in enumerate(lst, 1):
            scores[coach_id] = scores.get(coach_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]


def _rank_to_relevance(ordered_ids: list[int]) -> dict[int, float]:
    """排名 → 0~1 相关度（线性衰减：rank1=1.0，rankN=1/N）。"""
    total = len(ordered_ids)
    if total == 0:
        return {}
    return {cid: (total - i) / total for i, cid in enumerate(ordered_ids)}


def _apply_rerank(
    query: str, ordered_ids: list[int], coach_map: dict[int, dict[str, Any]]
) -> list[int]:
    """可选：对 RRF 排序后的 Top 列表做 Cross-Encoder 精排，返回重排后的 id 顺序。

    依赖缺失 / 关闭时 reranker.rerank() 本身会 no-op 原样返回，这里再兜一层。
    """
    docs = [
        {"coach_id": cid, "text": _coach_text(coach_map[cid])}
        for cid in ordered_ids
        if cid in coach_map
    ]
    reranked = reranker.rerank(query, docs, top_n=len(docs))
    return [int(d["coach_id"]) for d in reranked]


def hybrid_match_scores(query: str, coaches: list[dict[str, Any]]) -> dict[int, float]:
    """混合检索：返回 {coach_id: 0~1 相关度}，用于覆盖 score_match 的语义匹配维。

    返回空 dict 表示「混合检索不可用/无召回」，调用方应退回子串匹配。
    """
    query = (query or "").strip()
    if not settings.hybrid_retrieval_enabled or not query:
        return {}

    idset = {int(c["coach_id"]) for c in coaches}
    coach_map = {int(c["coach_id"]): c for c in coaches}

    # —— 三路召回（当前向量路自动退化，只走 BM25）——
    bm25_hits = [(cid, s) for cid, s in bm25.search(query, settings.bm25_top_k) if cid in idset]
    vec_hits = [
        (cid, s) for cid, s in vectorstore.search(query, settings.bm25_top_k) if cid in idset
    ]

    if not bm25_hits and not vec_hits:
        return {}

    if vec_hits:
        # 多路：RRF 融合（跨尺度）→ 排名转相关度
        fused = _rrf_fuse([bm25_hits, vec_hits], k=settings.rrf_k, top_k=settings.rrf_top_k)
        ordered_ids = [cid for cid, _ in fused]
    else:
        # 单路（轻量）：BM25 分数 min-max 归一化到 0~1（数据驱动，比排名对小列表更温和）
        max_s = max(s for _, s in bm25_hits)
        relevance = {cid: (s / max_s) if max_s > 0 else 0.0 for cid, s in bm25_hits}
        if settings.reranker_enabled:
            ordered_ids = _apply_rerank(query, list(relevance.keys()), coach_map)
            relevance = _rank_to_relevance(ordered_ids)
        return relevance

    # 多路分支的可选重排
    if settings.reranker_enabled:
        ordered_ids = _apply_rerank(query, ordered_ids, coach_map)

    return _rank_to_relevance(ordered_ids)


__all__ = ["hybrid_match_scores", "_rrf_fuse"]
