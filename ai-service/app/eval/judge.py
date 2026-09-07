"""LLM-as-Judge（#06 Harness 工程）：用便宜模型评判推荐理由质量。

什么时候用：规则能判的（长度/含教练名/空泛词）用 metrics.reason_quality_score 就够了；
规则难定义的（个性化/差异化/口语化）才上 LLM-as-Judge。原则：能用规则就不用 LLM。

mock 模式（无 API Key）下返回固定分数，保证离线可跑；真实 LLM 下返回 0~100 多维打分。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.clients.llm import achat, is_mock_mode

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """你是推荐理由质量评估员。请给以下理由打分（0~100），按维度评：
1. 个性化：是否结合用户具体目标（0~25）
2. 数据支撑：是否含评分/价格/擅长领域（0~25）
3. 差异化：是否点出至少 2 位教练的不同卖点（0~25）
4. 简洁度：是否 100 字以内（0~25）

用户目标：{user_goal}
候选教练：{candidates}
推荐理由：{reason}

只输出 JSON：{{"score": 0, "details": {{"个性化": 0, "数据支撑": 0, "差异化": 0, "简洁度": 0}}, "feedback": "一句话改进建议"}}
"""


async def judge_reason(user_goal: str, candidates: list[Any], reason: str) -> dict[str, Any]:
    """LLM 评判推荐理由质量。mock 模式返回固定分（离线可跑）。"""
    if is_mock_mode():
        return {"score": 80, "details": {}, "feedback": "mock judge（离线）"}

    candidates_brief = (
        "\n".join(
            f"- {getattr(c, 'name', c) if not isinstance(c, dict) else c.get('name', '')}"
            for c in candidates
        )
        or "（无）"
    )

    text = await achat(
        [
            {
                "role": "system",
                "content": JUDGE_PROMPT.format(
                    user_goal=user_goal, candidates=candidates_brief, reason=reason
                ),
            },
        ]
    )
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM-as-Judge 输出非 JSON，返回 0 分：%s", exc)
        return {"score": 0, "details": {}, "feedback": "judge 输出解析失败"}


__all__ = ["judge_reason"]
