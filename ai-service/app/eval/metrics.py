"""三类 Eval 指标（#06 Harness 工程）。

分节点评估（而非只评最终输出）——失败时能定位到具体节点：
  - intent_field_accuracy：Node1 意图抽取字段级准确率；
  - topk_hit_ratio：Node2 召回 Top-K 命中率；
  - reason_quality_score：Node3 推荐理由可读性/数据支撑。

原则（#06 §2.3）：能用规则的用规则，规则难定义的才上 LLM-as-Judge。
这三个指标都是纯规则、0 成本、可离线跑。
"""

from __future__ import annotations

from typing import Any

# 意图抽取关注的字段（expected 里这些字段非 None 才计入）
_INTENT_FIELDS = [
    "city_name",
    "district",
    "specialization",
    "level",
    "min_rating",
    "max_price",
    "time_slot",
    "male_only",
]


def intent_field_accuracy(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    fields: list[str] | None = None,
) -> float:
    """Node1 意图抽取字段级准确率（0~1）。

    expected 里为 None 的字段不计入（标注者没标的不参与打分）；
    time_slot 用模糊包含（"周末" 命中 "周末上午" 即算对）。
    """
    fields = fields or _INTENT_FIELDS
    correct, total = 0, 0
    for f in fields:
        exp = expected.get(f)
        if exp is None:
            continue
        total += 1
        pred = predicted.get(f)
        if f == "time_slot":
            if isinstance(exp, str) and exp.lower() in str(pred or "").lower():
                correct += 1
        elif pred == exp:
            correct += 1
    return correct / total if total else 1.0


def topk_hit_ratio(predicted_ids: list[int], expected_subset: list[int]) -> float:
    """Node2 召回 Top-K 命中率：期望的 coach_id 至少有一个出现在 Top-K（0 或 1）。"""
    if not expected_subset:
        return 1.0
    hit = any(eid in predicted_ids for eid in expected_subset)
    return 1.0 if hit else 0.0


# 空泛词表：只放「纯空话」信号。"推荐"不在内——"推荐李教练"是正常表达，不是空话。
_EMPTY_WORDS = ("很专业", "很棒", "非常好", "优秀", "靠谱", "值得", "无与伦比")


def reason_quality_score(reason: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Node3 推荐理由质量分（0~100）。返回 {score, details}。

    维度：长度(20) + 点出教练名(40) + 无空泛词(20) + 数据支撑(20)。
    """
    reason = reason or ""
    details: dict[str, int] = {}
    details["length"] = 20 if 30 <= len(reason) <= 200 else 0
    names_in = sum(1 for c in candidates if c.get("name", "") and c.get("name", "") in reason)
    details["coach_names"] = min(40, names_in * 20)
    details["no_empty"] = 20 if not any(w in reason for w in _EMPTY_WORDS) else 0
    details["data_richness"] = (
        20
        if any(str(c.get("rating")) in reason or str(c.get("price")) in reason for c in candidates)
        else 0
    )
    return {"score": sum(details.values()), "details": details}


__all__ = ["intent_field_accuracy", "topk_hit_ratio", "reason_quality_score"]
