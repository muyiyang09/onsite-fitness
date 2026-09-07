"""request_id / user_id 注入中间件（#05 · 结构化日志的关联键）。

给每个请求分配（或透传）request_id，并写入 contextvar，让该请求生命周期内所有日志
（含 Graph 节点）自动带上 request_id / user_id，实现一次请求的日志可串起来检索。

注意（Starlette 已知行为）：BaseHTTPMiddleware 里 set 的 contextvar 能传播到下游端点
（正向可用），但端点里 set 的反向传不回中间件。这里只在中间件 set、下游只读，故安全。
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import request_id_var, user_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", uuid4().hex)
        user_id = request.headers.get("x-user-id", "anon")

        request_id_var.set(request_id)
        user_id_var.set(user_id)

        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response


__all__ = ["RequestIdMiddleware"]
