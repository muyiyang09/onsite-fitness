-- =====================================================================
-- 上门体育 · 上门私教平台 数据库初始化脚本（v0.2，对齐后端 mapper XML）
-- 底座：脚手架 platform-backend
-- 14 张表：employee / user / address_book / category / coach /
--          coach_certificate / coach_schedule / course / course_package /
--          package_course / dispatch_pool / orders / order_detail / order_review
-- 注：CourseSpec 已并入 course（无独立表）；ShoppingCart 已删除
-- =====================================================================

DROP DATABASE IF EXISTS onsite_fitness;
CREATE DATABASE onsite_fitness DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE onsite_fitness;

-- ---------------------------------------------------------------------
-- 1. 平台管理员（复用脚手架 employee）
-- ---------------------------------------------------------------------
CREATE TABLE employee (
    id          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    username    VARCHAR(32) DEFAULT NULL COMMENT '账号',
    name        VARCHAR(32) DEFAULT NULL COMMENT '姓名',
    password    VARCHAR(64) DEFAULT NULL COMMENT '密码',
    phone       VARCHAR(16) DEFAULT NULL COMMENT '手机号',
    sex         VARCHAR(2)  DEFAULT NULL COMMENT '性别',
    id_number   VARCHAR(32) DEFAULT NULL COMMENT '身份证号',
    status      TINYINT     DEFAULT 1 COMMENT '状态 1启用 0禁用',
    role        VARCHAR(20) NOT NULL DEFAULT 'dev' COMMENT '角色 admin/dev（§6.27 RBAC）',
    create_time DATETIME    DEFAULT NULL COMMENT '创建时间',
    update_time DATETIME    DEFAULT NULL COMMENT '更新时间',
    create_user BIGINT      DEFAULT NULL COMMENT '创建人',
    update_user BIGINT      DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='平台管理员';

-- ---------------------------------------------------------------------
-- 2. 客户（复用脚手架 user）
-- ---------------------------------------------------------------------
CREATE TABLE user (
    id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    openid      VARCHAR(64)  DEFAULT NULL COMMENT '微信用户唯一标识',
    name        VARCHAR(32)  DEFAULT NULL COMMENT '姓名',
    phone       VARCHAR(16)  DEFAULT NULL COMMENT '手机号',
    sex         VARCHAR(2)   DEFAULT NULL COMMENT '性别 0 女 1 男',
    id_number   VARCHAR(32)  DEFAULT NULL COMMENT '身份证号',
    avatar      VARCHAR(255) DEFAULT NULL COMMENT '头像',
    create_time DATETIME     DEFAULT NULL COMMENT '注册时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='客户';

-- ---------------------------------------------------------------------
-- 3. 上门地址簿（复用脚手架 address_book）
-- ---------------------------------------------------------------------
CREATE TABLE address_book (
    id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id       BIGINT       NOT NULL COMMENT '用户id',
    consignee     VARCHAR(32)  DEFAULT NULL COMMENT '联系人',
    phone         VARCHAR(16)  DEFAULT NULL COMMENT '手机号',
    sex           VARCHAR(2)   DEFAULT NULL COMMENT '性别 0 女 1 男',
    province_code VARCHAR(12)  DEFAULT NULL COMMENT '省级区划编号',
    province_name VARCHAR(32)  DEFAULT NULL COMMENT '省级名称',
    city_code     VARCHAR(12)  DEFAULT NULL COMMENT '市级区划编号',
    city_name     VARCHAR(32)  DEFAULT NULL COMMENT '市级名称',
    district_code VARCHAR(12)  DEFAULT NULL COMMENT '区级区划编号',
    district_name VARCHAR(32)  DEFAULT NULL COMMENT '区级名称',
    detail        VARCHAR(255) DEFAULT NULL COMMENT '详细地址',
    label         VARCHAR(16)  DEFAULT NULL COMMENT '标签（家/公司）',
    is_default    TINYINT      DEFAULT 0 COMMENT '是否默认 0否 1是',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='上门地址';

-- ---------------------------------------------------------------------
-- 4. 课程分类（复用脚手架 category）
-- ---------------------------------------------------------------------
CREATE TABLE category (
    id          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    type        TINYINT     DEFAULT NULL COMMENT '类型 1课程分类 2套餐分类',
    name        VARCHAR(32) DEFAULT NULL COMMENT '分类名称',
    sort        INT         DEFAULT 0 COMMENT '顺序',
    status      TINYINT     DEFAULT 1 COMMENT '状态 0禁用 1启用',
    create_time DATETIME    DEFAULT NULL COMMENT '创建时间',
    update_time DATETIME    DEFAULT NULL COMMENT '更新时间',
    create_user BIGINT      DEFAULT NULL COMMENT '创建人',
    update_user BIGINT      DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='课程分类';

-- ---------------------------------------------------------------------
-- 5. 教练
-- ---------------------------------------------------------------------
CREATE TABLE coach (
    id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    openid            VARCHAR(64)  DEFAULT NULL COMMENT '教练端微信唯一标识',
    name              VARCHAR(32)  NOT NULL COMMENT '姓名',
    phone             VARCHAR(16)  DEFAULT NULL COMMENT '手机号',
    password          VARCHAR(64)  DEFAULT NULL COMMENT '登录密码',
    sex               VARCHAR(2)   DEFAULT NULL COMMENT '性别 0 女 1 男',
    avatar            VARCHAR(255) DEFAULT NULL COMMENT '头像',
    id_number         VARCHAR(32)  DEFAULT NULL COMMENT '身份证号',
    level             TINYINT      DEFAULT 1 COMMENT '等级 1初级 2中级 3高级 4金牌',
    rating            DECIMAL(2,1) DEFAULT 5.0 COMMENT '综合评分',
    service_radius_km DECIMAL(4,1) DEFAULT 5.0 COMMENT '服务半径(公里)',
    city_code         VARCHAR(12)  DEFAULT NULL COMMENT '服务城市区划编号',
    city_name         VARCHAR(32)  DEFAULT NULL COMMENT '服务城市名称',
    bio               VARCHAR(512) DEFAULT NULL COMMENT '简介/擅长',
    status            TINYINT      DEFAULT 0 COMMENT '状态 0待审核 1已审(正常) 2驳回(禁用)',
    create_time       DATETIME     DEFAULT NULL COMMENT '入驻时间',
    update_time       DATETIME     DEFAULT NULL COMMENT '更新时间',
    create_user       BIGINT       DEFAULT NULL COMMENT '创建人',
    update_user       BIGINT       DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='教练';

-- ---------------------------------------------------------------------
-- 6. 教练资质/证书
-- ---------------------------------------------------------------------
CREATE TABLE coach_certificate (
    id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    coach_id      BIGINT       NOT NULL COMMENT '教练id',
    cert_type     VARCHAR(32)  DEFAULT NULL COMMENT '证书类型（国职/ACE/NASM/NSCA等）',
    cert_no       VARCHAR(64)  DEFAULT NULL COMMENT '证书编号',
    image_url     VARCHAR(255) DEFAULT NULL COMMENT '证书图片',
    status        TINYINT      DEFAULT 0 COMMENT '审核状态 0待审核 1通过 2驳回',
    reject_reason VARCHAR(128) DEFAULT NULL COMMENT '驳回原因',
    create_time   DATETIME     DEFAULT NULL COMMENT '上传时间',
    update_time   DATETIME     DEFAULT NULL COMMENT '更新时间',
    audit_user    BIGINT       DEFAULT NULL COMMENT '审核人',
    audit_time    DATETIME     DEFAULT NULL COMMENT '审核时间',
    PRIMARY KEY (id),
    KEY idx_coach (coach_id)
) ENGINE=InnoDB COMMENT='教练资质';

-- ---------------------------------------------------------------------
-- 7. 教练排期
-- ---------------------------------------------------------------------
CREATE TABLE coach_schedule (
    id            BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    coach_id      BIGINT      NOT NULL COMMENT '教练id',
    schedule_date DATE        NOT NULL COMMENT '排期日期',
    time_slot     VARCHAR(32) NOT NULL COMMENT '时段(如 09:00-10:00)',
    status        TINYINT     DEFAULT 1 COMMENT '状态 1可约 2已占 3休息',
    order_id      BIGINT      DEFAULT NULL COMMENT '占用订单id',
    create_time   DATETIME    DEFAULT NULL COMMENT '创建时间',
    update_time   DATETIME    DEFAULT NULL COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_coach_date (coach_id, schedule_date)
) ENGINE=InnoDB COMMENT='教练排期';

-- ---------------------------------------------------------------------
-- 8. 课程（含规格字段，原 Dish + DishFlavor 合并）
-- ---------------------------------------------------------------------
CREATE TABLE course (
    id           BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    name         VARCHAR(64)   NOT NULL COMMENT '课程名称',
    category_id  BIGINT        DEFAULT NULL COMMENT '分类id',
    price        DECIMAL(10,2) DEFAULT NULL COMMENT '单次价格(元)',
    image        VARCHAR(255)  DEFAULT NULL COMMENT '封面图',
    description  VARCHAR(512)  DEFAULT NULL COMMENT '课程描述',
    status       TINYINT       DEFAULT 1 COMMENT '状态 0停售 1起售',
    intensity    VARCHAR(16)   DEFAULT NULL COMMENT '强度（轻/中/高）',
    duration_min INT           DEFAULT 60 COMMENT '时长(分钟)',
    suit_crowd   VARCHAR(255)  DEFAULT NULL COMMENT '适合人群',
    equipment    VARCHAR(255)  DEFAULT NULL COMMENT '所需器械(逗号分隔)',
    create_time  DATETIME      DEFAULT NULL COMMENT '创建时间',
    update_time  DATETIME      DEFAULT NULL COMMENT '更新时间',
    create_user  BIGINT        DEFAULT NULL COMMENT '创建人',
    update_user  BIGINT        DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='课程';

-- ---------------------------------------------------------------------
-- 9. 训练套餐（原 setmeal 改造）
-- ---------------------------------------------------------------------
CREATE TABLE course_package (
    id          BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    category_id BIGINT        DEFAULT NULL COMMENT '分类id',
    name        VARCHAR(64)   DEFAULT NULL COMMENT '套餐名称',
    price       DECIMAL(10,2) DEFAULT NULL COMMENT '套餐价格',
    image       VARCHAR(255)  DEFAULT NULL COMMENT '封面图',
    description VARCHAR(512)  DEFAULT NULL COMMENT '描述',
    status      TINYINT       DEFAULT 1 COMMENT '状态 0停售 1起售',
    create_time DATETIME      DEFAULT NULL COMMENT '创建时间',
    update_time DATETIME      DEFAULT NULL COMMENT '更新时间',
    create_user BIGINT        DEFAULT NULL COMMENT '创建人',
    update_user BIGINT        DEFAULT NULL COMMENT '修改人',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='训练套餐';

-- ---------------------------------------------------------------------
-- 10. 套餐课程关联（原 setmeal_dish 改造）
-- ---------------------------------------------------------------------
CREATE TABLE package_course (
    id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
    package_id  BIGINT   DEFAULT NULL COMMENT '套餐id',
    course_id   BIGINT   DEFAULT NULL COMMENT '课程id',
    course_num  INT      DEFAULT 1 COMMENT '套餐内该课程节数',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB COMMENT='套餐课程关联';

-- ---------------------------------------------------------------------
-- 11. 派单/抢单池（合并表，用 dispatch_type 区分）
-- ---------------------------------------------------------------------
CREATE TABLE dispatch_pool (
    id            BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_id      BIGINT      NOT NULL COMMENT '订单id',
    coach_id      BIGINT      DEFAULT NULL COMMENT '最终派给/抢到的教练',
    dispatch_type TINYINT     DEFAULT 0 COMMENT '派单类型 0待派 1系统派 2教练抢单',
    status        TINYINT     DEFAULT 0 COMMENT '状态 0待派 1已派 2已取消',
    city_code     VARCHAR(12) DEFAULT NULL COMMENT '服务城市编码(同城就近派单)',
    expire_time   DATETIME    DEFAULT NULL COMMENT '派单超时时间(兜底取消)',
    create_time   DATETIME    DEFAULT NULL COMMENT '进入派单池时间',
    dispatch_time DATETIME    DEFAULT NULL COMMENT '派单完成时间',
    PRIMARY KEY (id),
    KEY idx_order (order_id)
) ENGINE=InnoDB COMMENT='派单/抢单池';

-- ---------------------------------------------------------------------
-- 12. 预约订单（原 orders 改造）
-- ---------------------------------------------------------------------
CREATE TABLE orders (
    id                 BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_number       VARCHAR(64)   DEFAULT NULL COMMENT '订单号',
    status             TINYINT       DEFAULT 1 COMMENT '状态 1待付款 2待接单 3待服务 4服务中 5已完成 6已取消 7拒单 8退款中 9已退款 10已评价',
    user_id            BIGINT        NOT NULL COMMENT '下单用户id',
    coach_id           BIGINT        DEFAULT NULL COMMENT '教练id（指定单下单填/派单成功后回填）',
    address_book_id    BIGINT        DEFAULT NULL COMMENT '上门地址id',
    order_mode         TINYINT       DEFAULT NULL COMMENT '下单模式 1指定教练 2派单池',
    dispatch_type      TINYINT       DEFAULT NULL COMMENT '派单类型(派单池订单) 0待派 1系统派 2教练抢单',
    schedule_id        BIGINT        DEFAULT NULL COMMENT '预约排期id',
    schedule_date      DATE          DEFAULT NULL COMMENT '上门日期',
    time_slot          VARCHAR(32)   DEFAULT NULL COMMENT '上门时段(如 09:00-10:00)',
    consignee          VARCHAR(32)   DEFAULT NULL COMMENT '联系人',
    phone              VARCHAR(16)   DEFAULT NULL COMMENT '手机号',
    sex                VARCHAR(2)    DEFAULT NULL COMMENT '性别',
    address            VARCHAR(255)  DEFAULT NULL COMMENT '上门详细地址',
    amount             DECIMAL(10,2) DEFAULT NULL COMMENT '实收金额',
    pay_method         TINYINT       DEFAULT NULL COMMENT '支付方式 1微信 2支付宝',
    pay_status         TINYINT       DEFAULT 0 COMMENT '支付状态 0未支付 1已支付',
    submit_time        DATETIME      DEFAULT NULL COMMENT '下单时间',
    checkout_time      DATETIME      DEFAULT NULL COMMENT '支付时间',
    accept_time        DATETIME      DEFAULT NULL COMMENT '教练接单时间',
    service_start_time DATETIME      DEFAULT NULL COMMENT '服务开始时间',
    service_end_time   DATETIME      DEFAULT NULL COMMENT '服务完成时间',
    cancel_time        DATETIME      DEFAULT NULL COMMENT '取消时间',
    cancel_reason      VARCHAR(255)  DEFAULT NULL COMMENT '取消原因',
    rejection_reason   VARCHAR(255)  DEFAULT NULL COMMENT '拒单原因',
    remark             VARCHAR(255)  DEFAULT NULL COMMENT '用户备注',
    train_record       TEXT          COMMENT '训练记录(JSON)',
    body_data          TEXT          COMMENT '体测数据(JSON)',
    create_time        DATETIME      DEFAULT NULL COMMENT '创建时间',
    update_time        DATETIME      DEFAULT NULL COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_user (user_id),
    KEY idx_coach (coach_id)
) ENGINE=InnoDB COMMENT='预约订单';

-- ---------------------------------------------------------------------
-- 13. 订单明细（原 order_detail 改造）
-- ---------------------------------------------------------------------
CREATE TABLE order_detail (
    id               BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_id         BIGINT        NOT NULL COMMENT '订单id',
    course_id        BIGINT        DEFAULT NULL COMMENT '课程id',
    course_package_id BIGINT       DEFAULT NULL COMMENT '套餐id（套餐订单时填）',
    name             VARCHAR(64)   DEFAULT NULL COMMENT '名称(课程名/套餐名)',
    image            VARCHAR(255)  DEFAULT NULL COMMENT '图片',
    coach_id         BIGINT        DEFAULT NULL COMMENT '教练id',
    schedule_id      BIGINT        DEFAULT NULL COMMENT '排期id',
    schedule_date    DATE          DEFAULT NULL COMMENT '上门日期',
    time_slot        VARCHAR(32)   DEFAULT NULL COMMENT '上门时段',
    number           INT           DEFAULT 1 COMMENT '节数',
    amount           DECIMAL(10,2) DEFAULT NULL COMMENT '金额',
    create_time      DATETIME      DEFAULT NULL COMMENT '创建时间',
    update_time      DATETIME      DEFAULT NULL COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_order (order_id)
) ENGINE=InnoDB COMMENT='订单明细';

-- ---------------------------------------------------------------------
-- 14. 评价（教练 + 课程双维度）
-- ---------------------------------------------------------------------
CREATE TABLE order_review (
    id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
    order_id      BIGINT        NOT NULL COMMENT '订单id',
    user_id       BIGINT        NOT NULL COMMENT '用户id',
    coach_id      BIGINT        DEFAULT NULL COMMENT '教练id',
    course_id     BIGINT        DEFAULT NULL COMMENT '课程id',
    coach_rating  TINYINT       DEFAULT 5 COMMENT '教练评分 1-5',
    course_rating TINYINT       DEFAULT 5 COMMENT '课程评分 1-5',
    content       VARCHAR(512)  DEFAULT NULL COMMENT '评价内容',
    images        VARCHAR(1024) DEFAULT NULL COMMENT '图片(逗号分隔)',
    create_time   DATETIME      DEFAULT NULL COMMENT '评价时间',
    PRIMARY KEY (id),
    KEY idx_coach (coach_id),
    KEY idx_order (order_id)
) ENGINE=InnoDB COMMENT='评价';

-- ShedLock 分布式定时任务锁表（§6.24：多副本部署时防止 OrderTask 重复执行）
CREATE TABLE IF NOT EXISTS shedlock (
    name       VARCHAR(64)  NOT NULL COMMENT '锁名（如 order-task）',
    lock_until TIMESTAMP(3) NOT NULL COMMENT '锁到期时间',
    locked_at  TIMESTAMP(3) NOT NULL COMMENT '上锁时间',
    locked_by  VARCHAR(255) NOT NULL COMMENT '持锁实例标识',
    PRIMARY KEY (name)
) ENGINE=InnoDB COMMENT='ShedLock 分布式锁';

-- 业务审计日志表（§6.28：order.submit/seize/refund/handle、coachAudit 五类敏感动作）
CREATE TABLE IF NOT EXISTS sys_audit_log (
    id         BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
    user_id    BIGINT       DEFAULT NULL COMMENT '操作人id',
    type       VARCHAR(32)  NOT NULL COMMENT '动作类型 order.submit/seize/refund/handle/coachAudit',
    biz_id     BIGINT       DEFAULT NULL COMMENT '业务主键id（订单id/教练id等）',
    detail     VARCHAR(512) DEFAULT NULL COMMENT '操作描述',
    json_extra VARCHAR(1024) DEFAULT NULL COMMENT '扩展信息(JSON)',
    created_at DATETIME     DEFAULT NULL COMMENT '创建时间',
    PRIMARY KEY (id),
    KEY idx_type (type),
    KEY idx_biz (biz_id)
) ENGINE=InnoDB COMMENT='业务审计日志';

-- =====================================================================
-- 种子数据
-- =====================================================================

-- 平台管理员（密码 123456，BCrypt 哈希，与 EmployeeServiceImpl 的 BCryptPasswordEncoder 对齐；admin 角色）
INSERT INTO employee (id, username, name, password, phone, sex, status, role, create_time, update_time)
VALUES (1, 'admin', '平台管理员', '$2a$10$ZsEmKSJIKCkLTPE.hoZqneA4ZelvxAbbVLz0zG4UuR6qkKwFw7oL.', '13800000000', '1', 1, 'admin', NOW(), NOW());

-- 课程分类
INSERT INTO category (id, type, name, sort, status, create_time, update_time) VALUES
(1, 1, '减脂塑形', 1, 1, NOW(), NOW()),
(2, 1, '增肌训练', 2, 1, NOW(), NOW()),
(3, 1, '拉伸放松', 3, 1, NOW(), NOW()),
(4, 1, '产后恢复', 4, 1, NOW(), NOW()),
(5, 2, '减脂套餐', 1, 1, NOW(), NOW());

-- 课程
INSERT INTO course (id, name, category_id, price, image, description, status, intensity, duration_min, suit_crowd, equipment, create_time, update_time, create_user, update_user) VALUES
(1, '上门减脂私教课', 1, 199.00, NULL, '教练上门一对一科学减脂，含体测与训练计划', 1, '中', 60, '久坐上班族、体重超标人群', '弹力带,壶铃,瑜伽垫', NOW(), NOW(), 1, 1),
(2, '上门增肌训练课', 2, 229.00, NULL, '增肌塑形，提升基础代谢', 1, '高', 60, '健身入门者、体型偏瘦人群', '壶铃,哑铃,弹力带', NOW(), NOW(), 1, 1),
(3, '拉伸放松课', 3, 129.00, NULL, '全身拉伸、筋膜放松，缓解久坐酸痛', 1, '轻', 45, '办公室人群、运动后恢复', '瑜伽垫,泡沫轴', NOW(), NOW(), 1, 1),
(4, '产后恢复私教课', 4, 259.00, NULL, '产后核心修复、体态矫正', 1, '轻', 60, '产后妈妈', '瑜伽垫,弹力带', NOW(), NOW(), 1, 1);

-- 教练
INSERT INTO coach (id, openid, name, phone, password, sex, avatar, id_number, level, rating, service_radius_km, city_code, city_name, bio, status, create_time, update_time) VALUES
(1, NULL, '李教练', '13900000001', '$2a$10$ZsEmKSJIKCkLTPE.hoZqneA4ZelvxAbbVLz0zG4UuR6qkKwFw7oL.', '1', NULL, NULL, 4, 4.9, 8.0, '110100', '北京市', '国职认证，专注减脂塑形 8 年', 1, NOW(), NOW()),
(2, NULL, '王教练', '13900000002', '$2a$10$ZsEmKSJIKCkLTPE.hoZqneA4ZelvxAbbVLz0zG4UuR6qkKwFw7oL.', '2', NULL, NULL, 3, 4.8, 5.0, '110100', '北京市', '擅长增肌与体能训练', 1, NOW(), NOW()),
(3, NULL, '张教练', '13900000003', '$2a$10$ZsEmKSJIKCkLTPE.hoZqneA4ZelvxAbbVLz0zG4UuR6qkKwFw7oL.', '1', NULL, NULL, 2, 4.7, 10.0, '110100', '北京市', '运动康复方向，产后恢复经验丰富', 0, NOW(), NOW());

-- 教练资质
INSERT INTO coach_certificate (id, coach_id, cert_type, cert_no, image_url, status, reject_reason, create_time, update_time, audit_user, audit_time) VALUES
(1, 1, '国职', 'GZ20240001', NULL, 1, NULL, NOW(), NOW(), 1, NOW()),
(2, 2, 'ACE', 'ACE20240002', NULL, 1, NULL, NOW(), NOW(), 1, NOW()),
(3, 3, '运动康复师', 'KF20240003', NULL, 0, NULL, NOW(), NOW(), NULL, NULL);

-- 教练排期（近 3 天示例，时段用 09:00-10:00 格式）
INSERT INTO coach_schedule (id, coach_id, schedule_date, time_slot, status, order_id, create_time, update_time) VALUES
(1, 1, CURDATE() + INTERVAL 0 DAY, '09:00-10:00', 1, NULL, NOW(), NOW()),
(2, 1, CURDATE() + INTERVAL 0 DAY, '10:00-11:00', 1, NULL, NOW(), NOW()),
(3, 1, CURDATE() + INTERVAL 1 DAY, '09:00-10:00', 1, NULL, NOW(), NOW()),
(4, 1, CURDATE() + INTERVAL 2 DAY, '14:00-15:00', 1, NULL, NOW(), NOW()),
(5, 2, CURDATE() + INTERVAL 0 DAY, '10:00-11:00', 1, NULL, NOW(), NOW()),
(6, 2, CURDATE() + INTERVAL 1 DAY, '10:00-11:00', 1, NULL, NOW(), NOW());
