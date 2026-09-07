"""BM25 稀疏召回客户端（#04 RAG 升级的「关键词路」）。

背景：原 Node2 的语义匹配用 `bio.lower() 里做子串包含`，命中不了同义词/分词差异
（"产后恢复" 对不上 "孕产康复"）。BM25 用 jieba 分词 + 词频逆文档频率，对中文关键词
的召回更鲁棒，而且纯 Python、离线可跑、零运维。

设计取舍（为什么这样写）：
  1. 惰性构建索引 —— 首次 `search()` 才从 MySQL 拉 coach 表建索引，避免服务启动时
     强依赖 DB（DB 挂了服务照样起，只是降级为子串匹配）。
  2. 失败即降级 —— 建索引失败 / 查询失败一律返回 []，由上层 `hybrid.py` 决定退回
     子串匹配，绝不抛异常打断推荐主链路。
  3. 全量加载内存 —— 教练量级只有几百~几千，rank_bm25 全量内存索引足够，无需 ES。
  4. corpus 拼接 name + bio + city_name —— 让"李教练 减脂 北京"这种多维线索都能命中。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 轻量依赖：jieba（中文分词）+ rank_bm25（BM25Okapi 实现）。
# 已作为 #04 必选依赖写入 pyproject，但这里仍做保护性导入，避免缺失时拖垮整个服务。
try:
    import jieba  # type: ignore
    from rank_bm25 import BM25Okapi  # type: ignore

    _DEPS_OK = True
except ImportError as exc:  # pragma: no cover - 依赖缺失时的兜底
    logger.warning("[BM25] 缺失 jieba/rank_bm25，BM25 召回将降级为不可用：%s", exc)
    _DEPS_OK = False


class _BM25Index:
    """BM25 索引：coach_id 列表 + 分词后的 corpus + BM25 实例。"""

    def __init__(self, coaches: list[dict[str, Any]]) -> None:
        self.coach_ids: list[int] = [int(c["coach_id"]) for c in coaches]
        self.corpus: list[list[str]] = [
            _tokenize(f"{c.get('name', '')} {c.get('bio', '')} {c.get('city_name', '')}")
            for c in coaches
        ]
        self.bm25 = BM25Okapi(self.corpus)

    def search(self, query: str, top_k: int = 50) -> list[tuple[int, float]]:
        """返回 [(coach_id, bm25_score)]，按分数降序。分数为 BM25 原始值（越大越相关）。"""
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(zip(self.coach_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        # 过滤掉 0 分（无任何词命中的教练），避免把大量无关教练塞进候选
        ranked = [(cid, float(s)) for cid, s in ranked if s > 0]
        return ranked[:top_k]


def _tokenize(text: str) -> list[str]:
    """jieba 分词 + 去空白。空串返回 []。"""
    if not _DEPS_OK:
        return []
    return [t.strip() for t in jieba.cut(text or "") if t.strip()]


_index: _BM25Index | None = None


def _fetch_all_coaches_for_index() -> list[dict[str, Any]]:
    """从 MySQL 拉所有在售教练用于建索引。失败返回 []（上层走降级）。"""
    try:
        from app.clients.db import fetch_all

        rows = fetch_all("SELECT id, name, bio, city_name FROM coach WHERE status = 1")
        return [{"coach_id": int(r["id"]), **r} for r in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[BM25] 建索引取数失败，将降级为子串匹配：%s", exc)
        return []


def get_index() -> _BM25Index:
    """惰性获取全局 BM25 索引（首次调用建索引）。不可用时返回空索引（search 恒为空）。"""
    global _index
    if _index is None:
        coaches = _fetch_all_coaches_for_index()
        if coaches:
            try:
                _index = _BM25Index(coaches)
                logger.info("[BM25] 索引构建完成，coach 数=%d", len(coaches))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[BM25] 索引构建失败，降级：%s", exc)
                _index = _BM25Index([])
        else:
            _index = _BM25Index([])  # 空索引，search 恒返回 []
    return _index


def search(query: str, top_k: int = 50) -> list[tuple[int, float]]:
    """对外暴露的 BM25 召回接口。索引不可用 / 失败一律返回 []。"""
    if not _DEPS_OK or not (query or "").strip():
        return []
    try:
        return get_index().search(query, top_k)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[BM25] 召回失败，降级：%s", exc)
        return []


def rebuild_index() -> int:
    """强制重建索引（教练数据变更后调用）。返回索引教练数。"""
    global _index
    _index = None
    return len(get_index().coach_ids)


__all__ = ["search", "rebuild_index", "get_index"]
