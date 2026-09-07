"""Langfuse 接入冒烟测试（#13）：开态路径验证，无网络依赖（host 指向不可达端口，fail-open）。

用法：cd ai-service && python scripts/smoke_langfuse.py
期望输出：SMOKE OK（期间无未捕获异常）
"""
import asyncio
import os
import sys
from types import SimpleNamespace

os.environ["LANGFUSE_ENABLED"] = "true"
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-lf-smoke"
os.environ["LANGFUSE_SECRET_KEY"] = "sk-lf-smoke"
os.environ["LANGFUSE_HOST"] = "http://127.0.0.1:9"  # 不可达端口：连接立即被拒，验证 fail-open

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    # 1. import 整个 app：验证 FastAPI 路由注册接受 observe 装饰后的端点签名
    import app.main  # noqa: F401
    print("[1/4] app.main 导入成功（装饰器不影响路由签名解析）")

    from app.clients import langfuse_client

    # 2. 初始化（假 key + 不可达 host：初始化本身不联网，必须成功）
    assert langfuse_client.init_langfuse() is True, "init_langfuse 应成功"
    assert langfuse_client.langfuse_ready() is True
    print("[2/4] init_langfuse 成功")

    from app.clients.langfuse_client import (
        observe_span,
        update_current_generation,
        update_trace_meta,
    )

    @observe_span("llm.acompletion", as_type="generation")
    def fake_llm() -> str:
        resp = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18)
        )
        from app.clients.llm import _record_generation
        _record_generation(resp, "mock output")
        return "mock output"

    @observe_span("node.extract_intent")
    async def node() -> dict:
        await asyncio.sleep(0.01)
        fake_llm()
        return {"ok": True}

    @observe_span("api.smoke-root")
    async def root() -> None:
        update_trace_meta(
            user_id="u1", session_id="s1",
            metadata={"request_id": "req-smoke-1"}, tags=["smoke"],
        )
        await node()

    # 3. 三层嵌套：root → node → generation（span 树离线构建，不联网）
    asyncio.run(root())
    print("[3/4] 三层 span 树构建成功（api → node → generation + 真实 usage 上报）")

    # 4. flush（网络不可达：批量导出失败应被 SDK 内部吞掉，绝不抛出阻断停机）
    langfuse_client.flush_langfuse()
    print("[4/4] flush 完成（网络不可达未阻断停机，fail-open 验证通过）")
    print("SMOKE OK")


if __name__ == "__main__":
    main()
