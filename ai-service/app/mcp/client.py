"""MCP Client（#07 工具层）：让节点/Agent 通过 MCP 协议调工具，而非直接 import。

设计：默认不启用。`call_tool` 会尝试连 MCP Server；失败/未装 SDK 时抛异常，
由 `app.tools.registry.call_tool` 门面捕获并回退直接调用——协议层挂了不影响业务。
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_session = None


async def _get_session():
    """惰性连接 MCP Server（streamable-http）。"""
    global _session
    if _session is None:
        try:
            from mcp import ClientSession  # type: ignore
            from mcp.client.streamable_http import streamablehttp_client  # type: ignore
        except ImportError as exc:  # pragma: no cover - SDK 未装
            raise RuntimeError("未安装 mcp SDK，无法使用 MCP client（pip install mcp）") from exc

        client_ctx = streamablehttp_client(settings.mcp_server_url)
        read, write, _ = await client_ctx.__aenter__()
        session = ClientSession(read, write)
        await session.initialize()
        _session = session
        logger.info("MCP client 已连接：%s", settings.mcp_server_url)
    return _session


async def call_tool(name: str, args: dict[str, Any]) -> Any:
    """通过 MCP 调用工具。返回解析后的结果（JSON）。失败抛异常由上层回退。"""
    import json

    session = await _get_session()
    result = await session.call_tool(name, args)
    text = result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


__all__ = ["call_tool"]
