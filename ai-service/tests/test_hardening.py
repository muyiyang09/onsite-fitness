"""商业化加固（#05）单元测试：熔断器 / token 估算 / 缓存 key / 错误码。

纯函数 + 无 LLM/DB/Redis 依赖，可直接离线跑。

运行：
    cd ai-service
    ./.venv/Scripts/python.exe -m pytest tests/test_hardening.py -q
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_MOCK", "1")

from app.clients import cache as cache_module  # noqa: E402
from app.clients.cache import make_cache_key  # noqa: E402
from app.clients.circuit_breaker import CircuitBreaker, CircuitState  # noqa: E402
from app.core.exceptions import (  # noqa: E402
    LLMUnavailableError,
    RateLimitError,
    TokenBudgetExceededError,
)
from app.middleware.token_budget import estimate_tokens  # noqa: E402


# ---------------------------------------------------------------------------
# Token 估算
# ---------------------------------------------------------------------------
def test_estimate_tokens_cjk():
    # 中文 1 字符 ≈ 1 token（+1 兜底）
    assert estimate_tokens("减脂塑形") == 5


def test_estimate_tokens_english():
    # 英文 4 字符 ≈ 1 token（+1 兜底）
    assert estimate_tokens("abcd") == 2


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 1


# ---------------------------------------------------------------------------
# 缓存 key
# ---------------------------------------------------------------------------
def test_make_cache_key_stable_and_distinct():
    assert make_cache_key("减脂", 3, None) == make_cache_key("减脂", 3, None)
    assert make_cache_key("减脂", 3, None) != make_cache_key("增肌", 3, None)
    assert make_cache_key("减脂", 3, "北京市") != make_cache_key("减脂", 3, None)


# ---------------------------------------------------------------------------
# 熔断器
# ---------------------------------------------------------------------------
def test_circuit_breaker_opens_and_fails_fast():
    cb = CircuitBreaker(fail_threshold=2, reset_timeout=60)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            asyncio.run(cb.call(flaky))

    assert cb.state == CircuitState.OPEN
    assert calls["n"] == 2

    # OPEN 状态：快速失败，不再真正调用 fn
    with pytest.raises(RuntimeError):
        asyncio.run(cb.call(flaky))
    assert calls["n"] == 2  # 没再调 flaky


def test_circuit_breaker_recovers_after_timeout():
    cb = CircuitBreaker(fail_threshold=1, reset_timeout=60)

    async def flaky():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(cb.call(flaky))
    assert cb.state == CircuitState.OPEN

    # 模拟超时已过：半开试探成功 → 恢复闭合
    cb.last_fail_time = 0.0

    async def ok():
        return "ok"

    assert asyncio.run(cb.call(ok)) == "ok"
    assert cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# 错误码 → HTTP 状态
# ---------------------------------------------------------------------------
def test_exception_http_status():
    assert RateLimitError().http_status == 429
    assert TokenBudgetExceededError().http_status == 429
    assert LLMUnavailableError().http_status == 503


def test_exception_code_and_msg():
    e = RateLimitError()
    assert e.code == "AI_RATE_LIMIT"
    assert e.msg


# ---------------------------------------------------------------------------
# 缓存三防（§6.18）：雪崩 TTL 抖动 / 击穿 singleflight / 锁 CAS 释放
# ---------------------------------------------------------------------------
class _FakeRedis:
    """最小内存 Redis，只实现 cache.py 用到的方法，离线跑三防单测。"""

    def __init__(self, *args, **kwargs):
        self.store: dict[str, str] = {}  # key -> json str
        self.locks: dict[str, str] = {}  # lock key -> token
        self.setex_calls: list[tuple[str, int]] = []

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value
        self.setex_calls.append((key, ttl))

    async def set(self, key, token, nx=False, ex=None):
        if nx and key in self.locks:
            return False
        self.locks[key] = token
        return True

    async def eval(self, script, numkeys, *args):
        # _UNLOCK_LUA: KEYS[1]=lock_key, ARGV[1]=token → get==token 才 del
        key, token = args[0], args[1]
        if self.locks.get(key) == token:
            del self.locks[key]
            return 1
        return 0


def _patch_redis(monkeypatch, fake):
    monkeypatch.setattr(cache_module.redis, "Redis", lambda *a, **k: fake)


def test_ttl_jitter_range(monkeypatch):
    """雪崩防护：连续 20 次 set_cache，TTL 都落在 ±10% 抖动区间。"""
    fake = _FakeRedis()
    _patch_redis(monkeypatch, fake)

    async def run():
        for i in range(20):
            await cache_module.set_cache(f"k{i}", {"v": i}, ttl=1000)

    asyncio.run(run())
    assert len(fake.setex_calls) == 20
    for _, ttl in fake.setex_calls:
        assert 900 <= ttl <= 1100, f"TTL {ttl} 越出 ±10% 抖动区间"


def test_singleflight_single_build(monkeypatch):
    """击穿防护：并发 10 路只有抢到锁的那一路真正构图（≤2 次），其余复用结果。"""
    fake = _FakeRedis()
    _patch_redis(monkeypatch, fake)

    builds = {"n": 0}

    async def build_and_cache(key):
        token = await cache_module.try_acquire_build_lock(key)
        if token is None:
            cached = await cache_module.wait_for_result(key, budget=3.0)
            if cached:
                return cached
        builds["n"] += 1
        await asyncio.sleep(0.05)  # 模拟构图耗时
        result = {"v": 1}
        await cache_module.set_cache(key, result)
        await cache_module.release_build_lock(key, token)
        return result

    async def main():
        return await asyncio.gather(*[build_and_cache("hot-key") for _ in range(10)])

    results = asyncio.run(main())
    assert all(r == {"v": 1} for r in results)
    assert builds["n"] <= 2, f"graph 真实执行了 {builds['n']} 次，singleflight 失效"


def test_release_requires_token(monkeypatch):
    """锁 CAS 释放：错误 token 释放后锁仍在，正确 token 才删除（防 TOCTOU 误删）。"""
    fake = _FakeRedis()
    _patch_redis(monkeypatch, fake)

    async def run():
        key = "k"
        token = await cache_module.try_acquire_build_lock(key)
        assert token is not None

        await cache_module.release_build_lock(key, "wrong-token")
        assert fake.locks.get(f"{key}:lock") == token  # 锁未被误删

        await cache_module.release_build_lock(key, token)
        assert f"{key}:lock" not in fake.locks  # 正确 token 才删

    asyncio.run(run())
