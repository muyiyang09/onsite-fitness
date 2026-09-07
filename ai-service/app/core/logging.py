"""结构化 JSON 日志 + request_id/user_id 贯穿（#05 商业化加固）。

设计动机：生产环境多副本 + 海量日志，plain text 无法按 request_id 串起一次请求的完整链路。
改成 JSON 后可直接被 ELK / Loki / 云日志采集，`request_id` 作为贯穿全链路的关联键。

实现要点：
  - 用 `contextvars.ContextVar` 存 request_id / user_id，异步上下文安全（不同请求不串）；
  - 中间件在请求开始时 set，结束时 reset，所有 `logger.info/warning` 自动带上；
  - 单进程单次 setup，幂等（避免 uvicorn reload 时重复 addHandler）。
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar

# 贯穿请求上下文的关联键（中间件写入，日志 formatter 读取）
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class JsonFormatter(logging.Formatter):
    """把日志渲染成单行 JSON，便于采集与检索。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """幂等初始化根 logger：stdout + JSON formatter。"""
    global _configured
    if _configured:
        return
    # Windows GBK 控制台无法编码中文/emoji，强制 stdout 用 UTF-8（否则日志会 UnicodeEncodeError）
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    # 清掉可能已存在的默认 handler，避免重复输出
    root.handlers = [handler]
    _configured = True


__all__ = ["setup_logging", "request_id_var", "user_id_var", "JsonFormatter"]
