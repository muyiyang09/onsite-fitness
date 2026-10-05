-- §12.2 幂等防护索引 + §6.17 应用账号授权
-- 由 docker-entrypoint-initdb.d 自动执行（首启建库时生效）
-- 二次变更应走 Flyway（§17.1），本文件仅作为 baseline 的一部分

-- 1. 评价表 order_id 唯一索引（防止并发重评，§12.2）
ALTER TABLE order_review ADD UNIQUE INDEX uk_order_review_order_id (order_id);

-- 2. AI 评测反馈表 (request_id, action) 唯一索引（防止重复刷表，§12.2）
ALTER TABLE ai_eval_online ADD UNIQUE INDEX uk_eval_request_action (request_id, action);

-- 3. 派单池 order_id 唯一索引（防止重复入池，§6.8）
ALTER TABLE dispatch_pool ADD UNIQUE INDEX uk_dispatch_order_id (order_id);

-- 4. 应用账号权限收紧（§6.17）：MySQL docker 镜像已通过 MYSQL_USER 创建 sports_app
--    此处补充 GRANT 确保权限正确（若已由镜像自动授权则幂等）
GRANT SELECT, INSERT, UPDATE, DELETE ON onsite_fitness.* TO 'sports_app'@'%';
FLUSH PRIVILEGES;
