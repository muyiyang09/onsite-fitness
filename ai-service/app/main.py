"""FastAPI 服务入口：组装 app、注册中间件/异常处理/路由。

#05 商业化加固后：
  - 全链路异步（async 端点 + ainvoke + acompletion）；
  - /v1 版本前缀 + liveness(/healthz)/readiness(/readyz) 分离；
  - 结构化 JSON 日志 + request_id 贯穿 + 全局异常（错误码）；
  - 三级限流 + Token 预算 + 结果缓存 + 审计日志 + 优雅停机。

#05 §5.18 后：业务端点按资源拆分到 app/api/v1/*（system / recommend /
review_summary / cert_review / chat），本文件只保留组装与横切关注点。

启动：
    cd ai-service
    python -m pip install -e .      # 首次：装依赖
    cp .env.example .env            # 填 LLM_API_KEY（不填也能跑 mock）
    python -m app.main              # 或：uvicorn app.main:app --host 0.0.0.0 --port 18000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import cert_review, chat, recommend, review_summary, system
from app.clients import langfuse_client, redis_client
from app.clients.db import get_engine
from app.clients.llm import is_mock_mode
from app.config import settings
from app.core import metrics
from app.core.exceptions import AIError
from app.core.logging import request_id_var, setup_logging
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.service_auth import ServiceAuthMiddleware

logger = logging.getLogger("app.main")


# =============================================================================
# 生命周期：启动初始化 + 优雅停机
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(logging.INFO if settings.service_env != "dev" else logging.DEBUG)
    logger.info(
        "AI 服务启动：env=%s port=%s LLM=%s mock_mode=%s",
        settings.service_env,
        settings.service_port,
        settings.llm_model,
        is_mock_mode(),
    )

    # Langfuse 可观测性（#13，可选）：未启用/未装包/初始化失败一律降级为纯日志 trace（fail-open）
    if langfuse_client.init_langfuse():
        logger.info("[Langfuse] LLM 语义层 trace 已启用：节点 span + 真实 usage 上报（旁路异步）")

    # DB 灾备表建表（幂等，失败不阻断启动——Checkpointer 仍可用，只是 DB 兜底层会降级）
    if settings.checkpointer_backend == "redis" and settings.checkpoint_db_fallback:
        try:
            from app.core import session_store

            await session_store.ensure_table()
            logger.info("[SessionStore] ai_session_state 表已就绪（DB 灾备层激活）")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SessionStore] 建表失败（不影响启动，DB 兜底层降级为不可用）：%s", exc)

    yield
    # 优雅停机：先 flush Langfuse trace 队列（防丢尾巴），再清空连接池
    # （uvicorn --timeout-graceful-shutdown 已处理在飞请求层）
    logger.info("AI 服务停止：flush Langfuse + 关闭 DB/Redis 连接池")
    langfuse_client.flush_langfuse()
    try:
        get_engine().dispose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB 连接池关闭失败：%s", exc)
    await redis_client.close()


app = FastAPI(
    title="Sports Takeout · AI Service",
    description="体育外卖 · AI 微服务：教练智能推荐（LangGraph + LiteLLM + Pydantic）",
    version="0.2.0",
    lifespan=lifespan,
)


# CORS 来源（§6.31）：从 env ALLOWED_ORIGINS 解析；credentials=True 时禁止 "*"。
def _cors_origins() -> list[str]:
    raw = settings.cors_origins.strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()] if raw else []
    if settings.cors_allow_credentials:
        # 携带凭据时浏览器会拒绝 "Access-Control-Allow-Origin: *"，
        # 未显式配置则回退到开发前端常见来源（生产必须显式配置 ALLOWED_ORIGINS）。
        return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]
    return origins or ["*"]


# 中间件：后添加者更外层（先处理请求）。顺序：CORS(最外) → request_id → Service-Auth → 限流(最内)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ServiceAuthMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# 全局异常处理：把 AIError 统一转成 {code, msg, request_id}，不泄露内部栈
# =============================================================================
@app.exception_handler(AIError)
async def ai_error_handler(request: Request, exc: AIError) -> JSONResponse:
    metrics.incr("error_total")
    if exc.detail:
        logger.warning("AIError[%s] %s | detail=%s", exc.code, exc.msg, exc.detail)
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "msg": exc.msg, "request_id": request_id_var.get()},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：未预期的异常也返回结构化错误码，绝不裸 500 + 堆栈。"""
    metrics.incr("error_total")
    logger.exception("未预期异常：%s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "code": "AI_INTERNAL",
            "msg": "AI 服务内部错误",
            "request_id": request_id_var.get(),
        },
    )


# =============================================================================
# 业务路由：按资源拆分（§5.18）
# =============================================================================
app.include_router(system.router)
app.include_router(recommend.router)
app.include_router(review_summary.router)
app.include_router(cert_review.router)
app.include_router(chat.router)


# =============================================================================
# 脚本模式：python -m app.main 时直接启动 uvicorn
# =============================================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.service_env == "dev",
    )
