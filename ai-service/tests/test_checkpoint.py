"""Checkpointer 构建 + DB 灾备层测试（上线加固）。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_checkpoint.py -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.core.checkpoint import build_checkpointer  # noqa: E402
from app.core.checkpoint_redis_db import RedisDBCheckpointer  # noqa: E402


def _async_return(value):
    async def _fn(*args, **kwargs):
        return value

    return _fn


# ---------------------------------------------------------------------------
# Checkpointer 构建
# ---------------------------------------------------------------------------
def test_build_checkpointer_memory_default():
    from langgraph.checkpoint.memory import MemorySaver

    assert isinstance(build_checkpointer(), MemorySaver)


def test_build_checkpointer_redis_no_db_fallback(monkeypatch):
    from langgraph.checkpoint.redis import AsyncRedisSaver

    monkeypatch.setattr(settings, "checkpointer_backend", "redis")
    monkeypatch.setattr(settings, "checkpoint_db_fallback", False)
    assert isinstance(build_checkpointer(), AsyncRedisSaver)


def test_build_checkpointer_redis_with_db_fallback(monkeypatch):
    # 默认 checkpoint_db_fallback=True → 返回 RedisDBCheckpointer（带 DB 灾备）
    monkeypatch.setattr(settings, "checkpointer_backend", "redis")
    assert isinstance(build_checkpointer(), RedisDBCheckpointer)


# ---------------------------------------------------------------------------
# RedisDBCheckpointer DB 灾备层
# ---------------------------------------------------------------------------
class _FakeInner:
    def __init__(self, hit=None):
        self._hit = hit
        self.puts = []  # 记录 aput 调用

    async def aget_tuple(self, config):
        return self._hit

    async def aput(self, config, checkpoint, metadata, new_versions):
        self.puts.append((config, checkpoint, metadata))
        return config


def test_redis_db_checkpointer_redis_hit_no_db_read():
    inner = _FakeInner(hit=("hit",))
    cb = RedisDBCheckpointer(inner)
    result = asyncio.run(cb.aget_tuple({"configurable": {"thread_id": "t1"}}))
    assert result == ("hit",)
    assert inner.puts == []  # 命中不写


def test_redis_db_checkpointer_db_fallback_backfills(monkeypatch):
    import app.core.session_store as ss

    fake_state = {"checkpoint": {"v": 1, "id": "c1"}, "metadata": {"source": "input"}}
    monkeypatch.setattr(ss, "get_state", _async_return(fake_state))
    monkeypatch.setattr(ss, "put_state", _async_return(None))

    inner = _FakeInner(hit=None)
    cb = RedisDBCheckpointer(inner)
    result = asyncio.run(cb.aget_tuple({"configurable": {"thread_id": "t1"}}))

    assert result is not None
    assert result.checkpoint == {"v": 1, "id": "c1"}
    assert len(inner.puts) == 1  # 命中 DB 后回填 Redis


def test_redis_db_checkpointer_db_miss_empty_cache(monkeypatch):
    import app.core.session_store as ss

    monkeypatch.setattr(ss, "get_state", _async_return(None))

    inner = _FakeInner(hit=None)
    cb = RedisDBCheckpointer(inner)
    result = asyncio.run(cb.aget_tuple({"configurable": {"thread_id": "t1"}}))
    assert result is None


def test_redis_db_checkpointer_aput_dual_write(monkeypatch):
    import app.core.session_store as ss

    monkeypatch.setattr(ss, "put_state", _async_return(None))

    inner = _FakeInner(hit=None)
    cb = RedisDBCheckpointer(inner)
    cfg = {"configurable": {"thread_id": "t1"}}
    asyncio.run(cb.aput(cfg, {"v": 1}, {"source": "input"}, {}))

    assert len(inner.puts) == 1  # Redis 写成功
