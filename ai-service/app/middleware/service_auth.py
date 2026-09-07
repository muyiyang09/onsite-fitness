"""内部服务鉴权（§6.13）：后端 → ai-service 的机器间调用凭共享密钥校验。

纵深三层之一（内网隔离 + Service-Token + 后端代理客户端）：
  - 只保护 `/v1/` 前缀（业务端点）；`/healthz` `/readyz` `/metrics` 等探针路径不在此列，
    保持 liveness/readiness 探针可匿名访问；
  - 用 `hmac.compare_digest` 常量时间比较，避免时序侧信道；
  - 缺省 fail-closed：未配置 SERVICE_AUTH_TOKEN 时，所有 /v1/ 请求一律 401（生产必须配）。

dev 本地直调：把 `SERVICE_AUTH_TOKEN` 打进 .env，生成方式
`python -c "import secrets;print(secrets.token_urlsafe(32))"`。
"""

from __future__ import annotations

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_PROTECTED = ("/v1/",)


class ServiceAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_PROTECTED):
            expected = os.getenv("SERVICE_AUTH_TOKEN", "")
            got = request.headers.get("X-Service-Token", "")
            if not expected or not hmac.compare_digest(got, expected):
                # 直接返回 401（不用 raise HTTPException，避免被全局 Exception handler 吞成 500）
                return JSONResponse(
                    status_code=401,
                    content={"code": "AI_UNAUTHORIZED", "msg": "unauthorized service token"},
                )
        return await call_next(request)


__all__ = ["ServiceAuthMiddleware"]
