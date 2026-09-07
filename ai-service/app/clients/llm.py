"""LLM 客户端：基于 LiteLLM 的统一封装。
用 OpenAI 兼容模式 + BaseChatModel 契约（参考经验 1674242），避免把「供应商选择」
和「Agent/工具编排」耦合：换模型只改 .env 的 LLM_MODEL/LLM_API_KEY，上层代码 0 改动。
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Iterable
from typing import Any, Optional, Type, TypeVar, cast

from litellm import acompletion, completion
from pydantic import BaseModel, ValidationError

from app.clients.langfuse_client import (
    langfuse_ready,
    observe_span,
    update_current_generation,
)
from app.config import settings
from app.core import metrics
from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _record_generation(resp: Any, output: str) -> None:
    """把一次 LLM 调用的输出与真实 usage 上报到当前 Langfuse generation（#13）。

    - usage 取 API 返回的 resp.usage（真实账单），替代审计层的 estimate_tokens 估算；
    - 仅在 Langfuse 启用时生效；任何异常按 fail-open 静默降级（观测不影响业务）。
    """
    if not langfuse_ready():
        return
    usage_dict: Optional[dict[str, Any]] = None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        p = getattr(usage, "prompt_tokens", 0) or 0
        c = getattr(usage, "completion_tokens", 0) or 0
        t = getattr(usage, "total_tokens", 0) or (p + c)
        usage_dict = {"input": p, "output": c, "total": t, "unit": "TOKENS"}
    update_current_generation(
        output=output,
        model=settings.llm_model,
        usage=usage_dict,
        metadata={"request_id": request_id_var.get()},
    )

# =============================================================================
# 通用参数：所有 LLM 请求走同一组配置，保证行为一致
# =============================================================================
def _common_kwargs() -> dict[str, Any]:
    kw: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout,
        "num_retries": settings.llm_max_retries,
    }
    if settings.llm_api_key:
        kw["api_key"] = settings.llm_api_key
    if settings.llm_base_url:
        kw["api_base"] = settings.llm_base_url
    return kw


def _strip_text(text: Any) -> str:
    return (str(text) if text is not None else "").strip()


# =============================================================================
# 1. 普通文本生成
# =============================================================================
@observe_span("llm.completion", as_type="generation")
def chat(messages: Iterable[dict[str, str]]) -> str:
    """同步调用 LLM，返回纯文本回答。"""
    msgs = [
        {"role": m["role"], "content": _strip_text(m.get("content", ""))}
        for m in messages
    ]
    resp = completion(messages=msgs, **_common_kwargs())
    try:
        text = _strip_text(resp.choices[0].message.content)
    except (AttributeError, IndexError, KeyError) as exc:
        logger.error("LLM 返回结构异常: %s | resp=%s", exc, resp)
        raise RuntimeError(f"LLM 返回结构异常：{exc}") from exc
    _record_generation(resp, text)
    return text


@observe_span("llm.acompletion", as_type="generation")
async def achat(messages: Iterable[dict[str, str]]) -> str:
    msgs = [
        {"role": m["role"], "content": _strip_text(m.get("content", ""))}
        for m in messages
    ]
    metrics.incr("llm_calls_total")
    start = time.perf_counter()
    try:
        resp = await acompletion(messages=msgs, **_common_kwargs())
    finally:
        metrics.observe("llm_latency_ms", (time.perf_counter() - start) * 1000)
    try:
        text = _strip_text(resp.choices[0].message.content)
    except (AttributeError, IndexError, KeyError) as exc:
        logger.error("LLM 返回结构异常: %s | resp=%s", exc, resp)
        raise RuntimeError(f"LLM 返回结构异常：{exc}") from exc
    _record_generation(resp, text)
    return text


# =============================================================================
# 2. 结构化输出（Pydantic）—— 带结构适配层（经验 100036121）
# =============================================================================
def normalize_for_pydantic(raw: Any, expected_root_type: Type[T]) -> dict[str, Any]:
    """把 LLM 可能漂移的输出收敛成 schema 期望的 dict。

    核心规则（来自经验 100036121）：
      1) 顶层 list → 自动包进已知承载字段(candidates/items...)；
      2) 字段名别名/大小写漂移 → 按映射表收敛到 schema 标准字段名；
      3) 缺失 list 字段 → 填 []，避免必填校验硬失败。
    """
    # 规则 1：顶层 list 先包一层
    if isinstance(raw, list):
        fields = set(expected_root_type.model_fields.keys())
        for key in ("candidates", "coach_ids", "items", "results", "data", "top_coaches"):
            if key in fields:
                raw = {key: raw}
                break
        else:
            raw = raw[0] if raw else {}

    if not isinstance(raw, dict):
        raise ValueError(
            f"归一化失败：raw={type(raw).__name__} 无法转 dict，raw 前 200={str(raw)[:200]!r}"
        )

    # 规则 2：字段别名映射（教练推荐相关常见别名）
    alias_map: dict[str, tuple[str, ...]] = {
        "coach_ids": ("coachIdList", "coach_ids", "coachId", "coaches", "coach"),
        "recommend_reason": ("recommend_reason", "reason", "why", "summary", "reasoning"),
        "specialization_tags": ("tags", "labels", "specialization", "skills", "擅长领域"),
        "specialization": ("specialization", "speciality", "domain", "targets", "目标"),
        "district": ("district", "area", "region", "neighborhood", "区域"),
        "time_slot": ("time_slot", "slot", "schedule", "appointmentTime", "时段"),
        "city_name": ("city_name", "city", "城市"),
        "max_price": ("max_price", "priceMax", "budget", "预算"),
        "min_rating": ("min_rating", "ratingMin", "评分"),
        "level": ("level", "level_required", "等级"),
    }
    fields = set(expected_root_type.model_fields.keys())
    normalized: dict[str, Any] = {}
    for canonical, aliases in alias_map.items():
        if canonical in fields and canonical not in raw:
            for alias in aliases:
                if alias in raw and raw[alias] is not None:
                    normalized[canonical] = raw[alias]
                    break
    # 其他字段原样 copy
    normalized.update({k: v for k, v in raw.items() if k not in normalized})

    # 规则 3：缺失 list 类型字段默认 []
    for name, field_info in expected_root_type.model_fields.items():
        if name in normalized:
            continue
        annotation = str(field_info.annotation)
        if annotation.startswith("list") or "list[" in annotation or "List[" in annotation:
            normalized[name] = []
    return normalized


def _build_structured_messages(messages: Iterable[dict[str, str]], output_schema: Type[T]) -> list[dict[str, str]]:
    """把 JSON Schema 拼进 system prompt，作为结构化输出的约束。"""
    schema_json = output_schema.model_json_schema()
    system_with_schema = (
        "你是一个严格的 JSON 生成器。只根据给定的 JSON Schema 输出结果，"
        "不要有任何解释、Markdown、反引号、额外字符或嵌套代码块。\n"
        f"JSON Schema:\n{json.dumps(schema_json, ensure_ascii=False)}\n"
        "直接输出满足 schema 的 JSON object。"
    )
    return [{"role": "system", "content": system_with_schema}, *list(messages)]


def _parse_structured(raw_text: str, output_schema: Type[T]) -> T:
    """解析 LLM 文本 → dict → 归一化 → Pydantic 校验。失败抛 RuntimeError/ValidationError。"""
    parsed: Any
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned = (
            raw_text.strip()
            .removeprefix("```json")
            .removeprefix("```JSON")
            .removesuffix("```")
            .strip()
        )
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "结构化 JSON 解析失败。原始前 400 字=%s | exc=%s",
                raw_text[:400],
                exc,
            )
            raise RuntimeError(
                f"LLM 输出非合法 JSON：{exc}。前400字={raw_text[:400]}"
            ) from exc

    data = normalize_for_pydantic(parsed, output_schema)
    try:
        return output_schema.model_validate(data)
    except ValidationError as exc:
        logger.error(
            "Pydantic 校验失败：normalized=%s | errors=%s",
            data,
            exc.errors(),
        )
        raise


def chat_structured(messages: Iterable[dict[str, str]], output_schema: Type[T]) -> T:
    """结构化输出（同步）：JSON Schema 提示词 + 代码侧归一化 + Pydantic 校验。"""
    msgs = _build_structured_messages(messages, output_schema)
    return _parse_structured(chat(msgs), output_schema)


async def achat_structured(messages: Iterable[dict[str, str]], output_schema: Type[T]) -> T:
    """结构化输出（异步）：用 acompletion，避免阻塞事件循环。"""
    msgs = _build_structured_messages(messages, output_schema)
    return _parse_structured(await achat(msgs), output_schema)


async def achat_structured_with_retry(
    messages: Iterable[dict[str, str]],
    output_schema: Type[T],
    max_retries: int = 2,
) -> T:
    """带修正提示重试的结构化输出（异步）。

    关键：与 LiteLLM 内置 num_retries 分层——内置只处理 HTTP 层重试，
    这里处理「格式错误 / schema 校验失败」这类业务层错误：每次把错误喂回 LLM，
    让它看到自己上次错在哪，再输出一次。耗尽后抛最后异常，由调用方走 mock 兜底。
    """
    all_messages = list(messages)
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await achat_structured(all_messages, output_schema)
        except (RuntimeError, ValidationError) as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            correction = (
                f"你上次的输出有问题：{exc!s}\n"
                "请严格按 JSON Schema 重新输出，不要包含任何 markdown 或多余字符。"
            )
            all_messages = all_messages + [{"role": "user", "content": correction}]
            logger.warning("[achat_structured] 第 %d 次失败，带修正重试：%s", attempt + 1, exc)

    assert last_exc is not None
    raise last_exc


# =============================================================================
# 3. Mock（离线 demo：没配 api_key 或 AI_MOCK=1 时自动走假数据）
# =============================================================================
def is_mock_mode() -> bool:
    if os.environ.get("AI_MOCK", "").lower() in {"1", "true", "yes", "on"}:
        return True
    return not settings.llm_api_key


def is_mock_db() -> bool:
    """是否强制用本地 mock 教练/课程库（不读 MySQL）。

    与 is_mock_mode 区分：AI_MOCK 只 mock LLM；AI_MOCK_DB 只 mock 数据。
    Eval / 冒烟测试同时开两个，得到「完全离线、确定性」的结果，不依赖 MySQL 状态。
    """
    return os.environ.get("AI_MOCK_DB", "").lower() in {"1", "true", "yes", "on"}


def mock_structured(output_schema: Type[T], fallback: Optional[T] = None) -> T:
    if fallback is not None:
        return fallback
    defaults: dict[str, Any] = {}
    for name, field_info in output_schema.model_fields.items():
        if field_info.default is not None:
            defaults[name] = field_info.default
        elif "list[" in str(field_info.annotation):
            defaults[name] = []
    return cast(T, output_schema.model_construct(**defaults))
