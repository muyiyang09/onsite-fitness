"""clients 包：外部客户端（LLM / MySQL / Redis 等）。

当前只有一个 LLM 客户端，统一从 `app.clients.llm` re-export，
保证「单一来源」，避免在 __init__.py 里再维护一份会漂移的副本。
"""

from app.clients.llm import (  # noqa: F401
    achat,
    chat,
    chat_structured,
    is_mock_mode,
    mock_structured,
    normalize_for_pydantic,
)

__all__ = [
    "chat",
    "achat",
    "chat_structured",
    "normalize_for_pydantic",
    "is_mock_mode",
    "mock_structured",
]
