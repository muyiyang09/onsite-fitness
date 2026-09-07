"""安全与对齐（#10 §1.5）：Prompt 注入防御 + 输入消毒 + 工具分级。

教练推荐是低风险场景（最坏结果是推荐不准，不是越权/泄露），所以这里做**轻量但完整**的防护：
  - sanitize_input：去控制字符，防止脏输入污染 prompt；
  - wrap_user_input：用 `<user_input>` 标签包裹用户输入，隔离潜在注入（#02 §9）；
  - detect_injection：关键词启发式检测明显注入（只告警 + 审计，不粗暴拒绝——低风险场景）；
  - 工具分级：READ / WRITE / DANGEROUS，DANGEROUS 强制 HITL（#10 §1.5.4）。

局限说明（诚实）：关键词启发式不是银弹，真正强对抗要用 LLM-as-Judge 或内容安全 API。
这里覆盖 OWASP 常见的直接注入话术，够用但不承诺 100%。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 工具分级（#10 §1.5.4）：READ 只读可自由调 / WRITE 有副作用 / DANGEROUS 强制 HITL
TOOL_LEVEL_READ = "READ"
TOOL_LEVEL_WRITE = "WRITE"
TOOL_LEVEL_DANGEROUS = "DANGEROUS"

# 常见提示词注入特征（#10 §1.5.2 OWASP 常见直接注入话术）
_INJECTION_PATTERNS = (
    "忽略之前",
    "忽略以上",
    "忽略所有",
    "ignore previous",
    "ignore all",
    "system prompt",
    "系统提示",
    "你的指令",
    "越狱",
    "扮演",
    "reveal your instructions",
    "不要遵守",
    "你是另一个",
)


def sanitize_input(text: str | None) -> str:
    """消毒用户输入：去控制字符（保留 \n\t）、去首尾空白。"""
    if text is None:
        return ""
    cleaned = "".join(ch for ch in str(text) if ch >= " " or ch in "\n\t")
    return cleaned.strip()


def wrap_user_input(text: str) -> str:
    """用 `<user_input>` 标签包裹用户输入，隔离潜在注入（#02 §9 输入隔离）。"""
    return f"<user_input>\n{sanitize_input(text)}\n</user_input>"


def detect_injection(text: str | None) -> bool:
    """关键词启发式检测明显注入特征。命中返回 True（用于告警/审计，非粗暴拒绝）。"""
    t = (text or "").lower()
    return any(p in t for p in _INJECTION_PATTERNS)


def assert_tool_level(level: str, required: str) -> None:
    """工具分级校验：调用工具前确认其等级不越权。DANGEROUS 需人工确认。"""
    order = {TOOL_LEVEL_READ: 0, TOOL_LEVEL_WRITE: 1, TOOL_LEVEL_DANGEROUS: 2}
    if order.get(level, 0) > order.get(required, 2):
        raise PermissionError(f"工具等级 {level} 越权调用（需要 ≤ {required}）")


__all__ = [
    "sanitize_input",
    "wrap_user_input",
    "detect_injection",
    "assert_tool_level",
    "TOOL_LEVEL_READ",
    "TOOL_LEVEL_WRITE",
    "TOOL_LEVEL_DANGEROUS",
]
