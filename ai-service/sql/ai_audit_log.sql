-- ai-service 审计日志表（#05 商业化加固 · 合规/成本溯源）
-- 用途：记录所有 LLM / 工具调用，用于合规审计 + token 成本回溯 + 问题定位。
-- 执行：在 onsite_fitness 库下执行本文件即可（表不存在时 ai-service 会告警，不影响主流程）。

CREATE TABLE IF NOT EXISTS `ai_audit_log` (
    `id`            VARCHAR(36)  NOT NULL COMMENT 'UUID 主键',
    `user_id`       VARCHAR(64)  NOT NULL DEFAULT 'anon' COMMENT '用户 ID（匿名请求为 anon）',
    `request_id`    VARCHAR(64)  NOT NULL DEFAULT '-' COMMENT '请求关联 ID（贯穿一次请求的日志）',
    `action`        VARCHAR(32)  NOT NULL COMMENT '动作：llm_call / tool_call / graph_invoke',
    `model`         VARCHAR(64)  DEFAULT NULL COMMENT 'LLM 模型标识',
    `prompt`        TEXT         COMMENT '输入（截断 1000 字符）',
    `response`      TEXT         COMMENT '输出（截断 1000 字符）',
    `input_tokens`  INT          NOT NULL DEFAULT 0 COMMENT '输入 token 估算',
    `output_tokens` INT          NOT NULL DEFAULT 0 COMMENT '输出 token 估算',
    `duration_ms`   INT          NOT NULL DEFAULT 0 COMMENT '耗时（毫秒）',
    `success`       TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否成功',
    `error`         TEXT         COMMENT '失败原因',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_request_id` (`request_id`),
    KEY `idx_user_created` (`user_id`, `created_at`),
    KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 服务审计日志';
