"""MCP Server（#07 工具层）：把工具注册表通过 MCP 协议对外暴露。

用途：让外部 LLM（Claude Desktop / Cursor / 其它 Agent）或 Java 后端通过标准协议
调用本服务的工具（查教练 / BM25 / 向量 / 重排）。

默认不启用：`mcp` SDK 未装（重依赖），且单 Agent 单进程直接调用够用。
装了 `mcp` 包后可 `python -m app.mcp.server` 启动 streamable-http Server。

启动：
    pip install mcp
    python -m app.mcp.server
"""

from __future__ import annotations

import logging

from app.tools.registry import TOOL_REGISTRY

logger = logging.getLogger(__name__)


def build_server():
    """构建 MCP Server（惰性 import mcp SDK）。未装 SDK 时抛 RuntimeError。"""
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as exc:  # pragma: no cover - SDK 未装
        raise RuntimeError("未安装 mcp SDK，无法启动 MCP Server（pip install mcp）") from exc

    mcp = FastMCP("onsite-fitness-ai-tools")

    # 把注册表里的每个工具动态注册到 MCP
    for meta in TOOL_REGISTRY.list_tools():
        name = meta["name"]

        # 闭包捕获 name，避免循环变量晚绑定
        def make_handler(tool_name: str):
            async def handler(**kwargs):
                return await TOOL_REGISTRY.call(tool_name, kwargs)

            return handler

        # FastMCP 用装饰器注册工具：description + schema 直接绑定
        mcp.add_tool(
            make_handler(name),
            name=name,
            description=meta["description"],
            input_schema=meta["inputSchema"],
        )

    logger.info("MCP Server 就绪，暴露 %d 个工具", len(TOOL_REGISTRY.names()))
    return mcp


def run() -> None:
    """启动 streamable-http MCP Server。"""
    server = build_server()
    server.run(transport="streamable-http")


if __name__ == "__main__":
    run()
