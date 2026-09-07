"""Embedding 客户端（#04 向量路，预留）。

当前采用「轻量降级方案」：bge-m3 模型约 2.3GB，国内下载困难，故本模块**默认不启用**，
只保留接口 + 惰性加载骨架，等有 GPU/可访问 HuggingFace 的环境再接入（改 .env 即可）。

设计要点：
  - 惰性加载：首次 `embed()` 才 import FlagEmbedding + 下载/加载模型，不拖慢服务启动；
  - 失败即降级：依赖缺失 / 模型加载失败时，`embed()` 返回空 numpy 数组，
    由上层 `vectorstore.py` / `hybrid.py` 判断为空并退回 BM25 单路，绝不抛异常。
"""

from __future__ import annotations

import logging

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model: object | None = None


def _get_model():
    """惰性加载本地 embedding 模型（首次调用可能耗时数秒~数十秒）。"""
    global _model
    if _model is None:
        # FlagEmbedding 是重依赖（会连带 torch/transformers，GB 级），不在默认依赖里。
        # 只在真的要用向量召回时才装，且用延迟 import 避免拖慢/拖垮其它路径。
        try:
            from FlagEmbedding import BGEM3FlagModel  # type: ignore
        except ImportError as exc:  # pragma: no cover - 重依赖未装
            logger.warning(
                "[Embedding] 未安装 FlagEmbedding（bge-m3 重依赖），向量召回不可用：%s", exc
            )
            raise RuntimeError("FlagEmbedding 未安装") from exc

        _model = BGEM3FlagModel(
            settings.embedding_model,
            use_fp16=settings.embedding_use_fp16,
            device=settings.embedding_device,
        )
        logger.info(
            "[Embedding] 模型加载完成：%s @ %s",
            settings.embedding_model,
            settings.embedding_device,
        )
    return _model


def embed(texts: list[str]) -> np.ndarray:
    """批量 embedding，返回 [N, dim] 的 numpy 数组。不可用时返回空数组（shape (0,)）。"""
    if not texts:
        return np.array([])
    try:
        result = _get_model().encode(texts, batch_size=32, max_length=512)["dense_vecs"]
        return np.array(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Embedding] embedding 失败，降级为空：%s", exc)
        return np.array([])


def embed_one(text: str) -> np.ndarray:
    """单条 embedding，返回 [dim]。不可用时返回空数组。"""
    vecs = embed([text])
    return vecs[0] if vecs.size else np.array([])


__all__ = ["embed", "embed_one"]
