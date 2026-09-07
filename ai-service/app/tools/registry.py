"""工具注册表 + 统一调用门面（#07 MCP 工具层核心）。

设计（为什么这样抽象）：
  - 工具 = name + description + JSON Schema + 异步 handler，一个工具干一件事；
  - 注册表是「单一事实来源」：节点、MCP Server、未来其它 Agent 都从这取工具；
  - `call_tool` 门面统一入口：MCP 启用时走 MCP client（跨语言/外部 LLM），失败或未启用
    时回退直接调用注册表——协议层挂了绝不拖垮业务（#07 §6 兜底原则）。

当前 MCP 默认关闭（单 Agent 单进程直接调用够用，见 #07 §2.2 决策树），
等 #08 多 Agent 落地 + 需要跨语言时再开。
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]  # 异步实现，args(**kwargs) -> Any
    level: str = "READ"  # 工具分级：READ / WRITE / DANGEROUS（#10 §1.5.4）


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def list_tools(self) -> list[dict[str, Any]]:
        """返回工具元数据（供 MCP tools/list 或启动时展示）。"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
                "level": t.level,
            }
            for t in self._tools.values()
        ]

    def get_level(self, name: str) -> str:
        return self._tools[name].level

    async def call(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"未知工具: {name}")
        return await self._tools[name].handler(**args)


# 全局注册表：各工具模块在 import 时往这里注册
TOOL_REGISTRY = ToolRegistry()


async def call_tool(name: str, args: dict[str, Any]) -> Any:
    """统一工具调用入口。MCP 启用时走 client（失败回退），否则直接走注册表。"""
    from app.config import settings
    from app.core import metrics

    metrics.incr("tool_calls_total")
    if settings.mcp_enabled:
        try:
            from app.mcp.client import call_tool as mcp_call

            return await mcp_call(name, args)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[tools] MCP 调用 %s 失败，回退直接调用：%s", name, exc)
    return await TOOL_REGISTRY.call(name, args)


__all__ = ["Tool", "ToolRegistry", "TOOL_REGISTRY", "call_tool"]
