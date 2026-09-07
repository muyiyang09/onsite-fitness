"""Rerank 客户端（#04 精排，预留）。

Cross-Encoder（bge-reranker-v2-m3）把 (query, doc) 拼一起过模型，精度比双塔高但慢 ~100 倍，
所以只用于「召回 Top30 → 精排 TopN」的精排阶段。当前「轻量降级方案」下默认不启用。

设计要点：
  - 惰性加载 + 失败降级：依赖缺失 / 模型加载失败时 `rerank()` 原样返回输入（no-op），
    由上层 hybrid.py 直接沿用 RRF 顺序，不抛异常。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_model: Any = None


def _get_model():
    """惰性加载 reranker 模型。依赖缺失时抛 RuntimeError（上层降级为 no-op）。"""
    global _model
    if _model is None:
        try:
            from FlagEmbedding import FlagReranker  # type: ignore
        except ImportError as exc:  # pragma: no cover - 重依赖未装
            logger.warning("[Reranker] 未安装 FlagEmbedding，重排不可用：%s", exc)
            raise RuntimeError("FlagEmbedding 未安装") from exc

        _model = FlagReranker(
            settings.reranker_model,
            use_fp16=settings.reranker_use_fp16,
            device=settings.reranker_device,
        )
    return _model


def rerank(query: str, docs: list[dict[str, Any]], top_n: int = 3) -> list[dict[str, Any]]:
    """按 query 相关性对 docs 精排，返回 top_n（保持原 dict 结构）。

    不可用 / 失败时**原样返回 docs[:top_n]**（no-op 降级），不改变上游顺序。
    docs 约定：[{"coach_id": 1, "text": "李教练 专注减脂 8 年", ...}, ...]
    """
    if not (query or "").strip() or not docs:
        return docs[:top_n]
    try:
        model = _get_model()
        pairs = [[query, d.get("text", "")] for d in docs]
        scores = model.compute_score(pairs, normalize=True)
        if not isinstance(scores, (list, tuple)):
            scores = [scores]  # 单条输入返回标量
        ranked = sorted(zip(docs, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked[:top_n]]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Reranker] 重排失败，跳过（沿用 RRF 顺序）：%s", exc)
        return docs[:top_n]


__all__ = ["rerank"]
