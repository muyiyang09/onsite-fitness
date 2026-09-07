"""工具注册表 + 工具调用测试（#07 MCP 工具层）。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_tools.py -q
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_MOCK", "1")
os.environ.setdefault("AI_MOCK_DB", "1")

from app.tools.coach_tools import fetch_coaches  # noqa: E402
from app.tools.registry import TOOL_REGISTRY, call_tool  # noqa: E402


def test_registry_registered_expected_tools():
    names = TOOL_REGISTRY.names()
    for expected in (
        "fetch_coaches",
        "fetch_courses",
        "bm25_search",
        "vector_search",
        "rerank_docs",
    ):
        assert expected in names


def test_registry_list_tools_schema():
    metas = TOOL_REGISTRY.list_tools()
    by_name = {m["name"]: m for m in metas}
    assert "description" in by_name["fetch_coaches"]
    assert "inputSchema" in by_name["bm25_search"]


def test_fetch_coaches_mock_db():
    coaches = asyncio.run(fetch_coaches(city_name=None))
    assert len(coaches) == 3  # mock 库 3 个教练


def test_call_tool_fetch_courses():
    courses = asyncio.run(call_tool("fetch_courses", {}))
    assert len(courses) == 3


def test_call_tool_unknown_raises():
    import pytest

    with pytest.raises(KeyError):
        asyncio.run(call_tool("nonexistent_tool", {}))
