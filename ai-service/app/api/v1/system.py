"""系统路由：liveness / readiness / metrics。"""

from __future__ import annotations

import asyncio
import logging

import redis.asyncio as redis
from fastapi import APIRouter
from fastapi.responses import Response

from app.clients import redis_client
from app.clients.db import is_db_available
from app.clients.llm import is_mock_mode
from app.config import settings
from app.core import metrics

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/healthz", summary="Liveness：进程是否活着（不查依赖）")
async def healthz() -> dict[str, object]:
    return {"ok": True, "env": settings.service_env, "mock_mode": is_mock_mode()}


@router.get("/readyz", summary="Readiness：是否准备好接流量（查 DB/Redis/LLM）")
async def readyz() -> dict[str, object]:
    checks: dict[str, str] = {}

    # DB
    try:
        db_ok = await asyncio.to_thread(is_db_available)
        checks["db"] = "ok" if db_ok else "down"
    except Exception:  # noqa: BLE001
        checks["db"] = "down"

    # Redis
    try:
        r = redis.Redis(connection_pool=redis_client.get_pool())
        await r.ping()
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "down"

    # LLM：mock 模式视为可用（离线兜底）
    checks["llm"] = "mock" if is_mock_mode() else "ok"

    ready = all(v in ("ok", "mock") for v in checks.values())
    return {"ok": ready, "checks": checks}


@router.get("/metrics", summary="Prometheus 指标导出")
async def metrics_endpoint() -> Response:
    """导出 Prometheus 文本格式指标（llm/tool/cache/error/latency）。"""
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4")
