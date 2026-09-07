"""会话状态 DB 灾备存储（Checkpointer DB 兜底层）。

Redis Checkpointer 的 TTL 到期时，会话 state 会丢、会话中断。这里用 MySQL 兜底：
  - put_state：Checkpointer 每次 put 时双写一份 JSON 到 DB；
  - get_state：Redis miss 时从这里读回，回填 Redis 继续会话。

设计：只做「thread_id → checkpoint JSON」的简单 KV，不关心 Checkpoint 内部结构，
序列化用 json.dumps(ensure_ascii=False, default=str)，非 JSON 类型降级为字符串。
"""

from __future__ import annotations

import json
import logging

from app.clients.db import aexecute, afetch_all

logger = logging.getLogger(__name__)

_TABLE = "ai_session_state"


async def ensure_table() -> None:
    """建表（幂等）。失败抛异常，由 main.py lifespan 捕获并降级（不影响启动）。"""
    await aexecute(f"""
        CREATE TABLE IF NOT EXISTS `{_TABLE}` (
            `thread_id`       VARCHAR(128) NOT NULL COMMENT '会话 thread_id',
            `checkpoint_json` TEXT         NOT NULL COMMENT 'CheckpointTuple 的 JSON',
            `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`thread_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        COMMENT='AI 会话状态灾备（Checkpointer DB 兜底）'
    """)


async def get_state(thread_id: str) -> dict | None:
    """读会话 state。无记录返回 None，JSON 损坏返回 None（并告警）。"""
    rows = await afetch_all(
        f"SELECT checkpoint_json FROM `{_TABLE}` WHERE thread_id = :t", {"t": thread_id}
    )
    if not rows:
        return None
    try:
        return json.loads(rows[0]["checkpoint_json"])
    except (json.JSONDecodeError, TypeError) as exc:  # noqa: BLE001
        logger.warning("会话状态 JSON 解析失败，thread_id=%s：%s", thread_id, exc)
        return None


async def put_state(thread_id: str, payload: dict) -> None:
    """写会话 state（upsert）。"""
    await aexecute(
        f"INSERT INTO `{_TABLE}` (thread_id, checkpoint_json) VALUES (:t, :j) "
        f"ON DUPLICATE KEY UPDATE checkpoint_json = :j, updated_at = NOW()",
        {"t": thread_id, "j": json.dumps(payload, ensure_ascii=False, default=str)},
    )


__all__ = ["ensure_table", "get_state", "put_state"]
