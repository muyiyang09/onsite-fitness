-- ai-service 在线反馈表（#06 Harness 工程 · 反馈回流）
-- 用途：记录用户对推荐结果的反馈（点赞/点踩/下单），作为在线 Eval 集 —— 用户真实行为
--       才是最强的 ground truth，定期聚合回离线 Eval 集，形成「线上回流 → 离线评估」闭环。
-- 执行：在 onsite_fitness 库下执行本文件即可。

CREATE TABLE IF NOT EXISTS `ai_eval_online` (
    `id`         BIGINT       NOT NULL AUTO_INCREMENT,
    `request_id` VARCHAR(64)  NOT NULL COMMENT '关联推荐请求的 request_id',
    `user_id`    VARCHAR(64)  NOT NULL DEFAULT 'anon' COMMENT '用户 ID',
    `action`     VARCHAR(16)  NOT NULL COMMENT '行为：like / dislike / order',
    `coach_id`   INT          DEFAULT NULL COMMENT '被点击/下单的教练 ID',
    `feedback`   TEXT         COMMENT '补充文字反馈',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_request_id` (`request_id`),
    KEY `idx_action_created` (`action`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 服务在线反馈（Eval 回流）';
