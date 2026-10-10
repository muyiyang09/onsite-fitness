# 上门体育 · 上门私教平台 — 部署指南

## 一、Docker Compose 一键部署（推荐）

### 前置条件
- 已安装 Docker 和 Docker Compose

### 步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yourname/onsite-fitness.git
cd onsite-fitness

# 2. 复制环境变量文件并修改
cp .env.example .env
# 编辑 .env —— 以下为必填项（缺任一项 compose 启动即报错）：
#   MYSQL_ROOT_PASSWORD      MySQL root 密码
#   MYSQL_APP_PASSWORD       应用账号 sports_app 密码（后端/ai-service 用它连库）
#   REDIS_PASSWORD           Redis 密码（已启用 requirepass）
#   MILVUS_MINIO_ACCESS_KEY / MILVUS_MINIO_SECRET_KEY   Milvus 内部对象存储凭据
# 建议同时填写：
#   ONSITE_JWT_ADMIN_KEY / ONSITE_JWT_USER_KEY / ONSITE_JWT_COACH_KEY / ONSITE_AES_KEY
#   SERVICE_AUTH_TOKEN       后端 ↔ ai-service 机器间鉴权共享密钥
#   LLM_API_KEY              AI 推荐链路 LLM Key

# 3. 一键启动（首次会自动构建镜像 + 初始化数据库）
docker-compose up -d

# 4. 查看启动状态
docker-compose ps

# 5. 查看后端日志
docker-compose logs -f backend
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 后端 API | http://localhost:8080 | Spring Boot + Knife4j |
| 接口文档 | http://localhost:8080/doc.html | Knife4j UI（生产 profile 自动关闭） |
| 管理端前端 | http://localhost:5173 | Vue3 + Element Plus |
| AI 微服务 | http://127.0.0.1:18000 | 仅本机可访问，不对公网暴露；需 x-service-token 鉴权 |
| Milvus | localhost:19530 | 向量库 gRPC（etcd + minio 三服务栈） |
| Attu（可选） | http://localhost:8001 | Milvus 可视化运维台 |
| MySQL | 127.0.0.1:3306 | 应用账号 sports_app / 密码见 .env；root 仅初始化用 |
| Redis | 127.0.0.1:6379 | 已启用 requirepass，密码见 .env |
| Prometheus | http://localhost:9090 | 指标采集 |
| Grafana | http://localhost:3000 | 可视化面板（admin/admin，上线请改密码） |
| Alertmanager | http://localhost:9093 | 告警路由 → 钉钉/飞书 webhook |

> 安全基线：MySQL/Redis/MinIO 控制台仅绑定 `127.0.0.1`；ai-service 的 `/v1/ai/*` 全部要求 `x-service-token` 头（与后端共享 SERVICE_AUTH_TOKEN）；JWT/AES 密钥一律走环境变量注入，缺省即启动失败。

### 默认管理员账号
- 用户名：admin
- 密码：123456

### 停止 / 清理

```bash
# 停止
docker-compose down

# 停止并删除数据卷（清空数据库）
docker-compose down -v
```

---

## 二、本地开发部署（不用 Docker）

### 前置条件
- JDK 21
- Maven 3.9+
- MySQL 8.0
- Redis 7+
- Node.js 18+

### 后端启动

```bash
# 1. 创建数据库并导入表结构
mysql -u root -p < sql/onsite_fitness.sql

# 2. 修改配置
# 编辑 platform-backend/backend-server/src/main/resources/application-dev.yml
# 修改数据库密码、Redis 地址等

# 3. 编译并启动
cd platform-backend
mvn clean package -DskipTests -q
java -jar backend-server/target/backend-server-*.jar
```

### 管理端前端启动

```bash
cd admin-web
npm install
npm run dev
# 访问 http://localhost:5173
```

### 小程序启动

1. 打开微信开发者工具
2. 导入 `uniapp-user` 目录（用户端）或 `uniapp-coach` 目录（教练端）
3. 修改 `utils/request.js` 中的 `baseUrl` 为你的后端地址

---

## 三、目录结构

```
onsite-fitness/
├── docker-compose.yml          # Docker Compose 编排（含 Milvus 三服务栈 + 可观测栈）
├── .env.example                # 环境变量模板（含必填项注释）
├── DEPLOY.md                   # 本文档
├── sql/onsite_fitness.sql     # 数据库建表 + 种子数据（14 张表）
├── sql/07-idempotency-indexes.sql  # 幂等唯一索引 + 应用账号授权
├── scripts/
│   ├── smoke_test.sh           # 端到端冒烟测试（CI/CD 回滚依据）
│   └── backup_mysql.sh         # MySQL 每日备份（gzip + 过期清理）
├── prometheus/
│   ├── prometheus.yml          # 采集配置
│   └── alertmanager.yml        # 告警路由配置
├── ai-service/                 # AI 微服务（FastAPI + LangGraph + Milvus）
│   ├── Dockerfile              # AI 服务容器构建
│   ├── .env.example            # AI 服务环境变量模板
│   └── app/                    # graphs / clients / middleware / core / eval / mcp / tools
├── platform-backend/               # 后端工程
│   ├── Dockerfile              # 后端容器构建
│   ├── backend-common/             # 公共模块（工具类/常量/异常）
│   ├── backend-model/               # 实体/DTO/VO
│   └── backend-server/             # Spring Boot 主工程
│       └── src/main/resources/
│           ├── application.yml         # 主配置
│           ├── application-dev.yml     # 开发环境配置
│           └── application-docker.yml  # Docker 环境配置
├── admin-web/                  # 管理端 PC 前端
│   ├── Dockerfile              # 前端容器构建
│   ├── nginx.conf              # Nginx 反向代理配置
│   └── src/views/
│       ├── LoginView.vue       # 登录页
│       ├── CoachView.vue       # 教练审核（含资质证书预览）
│       ├── CourseView.vue      # 课程管理（CRUD + 上下架）
│       ├── OrderView.vue       # 订单管理（搜索 + 详情）
│       └── DispatchPoolView.vue # 派单池监控
├── uniapp-user/                # 用户端小程序
└── uniapp-coach/               # 教练端小程序
```

---

## 四、运维脚本

```bash
# 端到端冒烟测试（任一失败 exit 1，可作为部署后自动回滚依据）
bash scripts/smoke_test.sh

# MySQL 每日备份（crontab 示例：每天凌晨 2 点）
0 2 * * * /opt/onsite-fitness/scripts/backup_mysql.sh
```

---

## 五、常见问题

### Q: 启动后接口返回 500？
A: 检查 MySQL 和 Redis 是否正常启动。后端日志会打印连接异常。

### Q: compose up 报 "required variable XXX is empty"？
A: `.env` 中缺少必填环境变量（MYSQL_ROOT_PASSWORD / MYSQL_APP_PASSWORD / REDIS_PASSWORD / MILVUS_MINIO_ACCESS_KEY 等），按 `.env.example` 注释补齐即可。

### Q: AI 接口返回 401？
A: `/v1/ai/*` 需要 `x-service-token` 请求头，值为后端与 ai-service 共享的 `SERVICE_AUTH_TOKEN`（见 .env）。

### Q: 管理端登录提示 401？
A: 确认后端已启动，且 `application-dev.yml` 中的数据库配置正确。默认账号 admin/123456。

### Q: 小程序请求被拒绝（ERR_CONNECTION_REFUSED）？
A: 检查后端是否在 8080 端口运行，且小程序的 `baseUrl` 配置正确。

### Q: 图片上传不成功？
A: 需要配置阿里云 OSS。在 `.env` 中填写 `ONSITE_OSS_AK` 和 `ONSITE_OSS_SK`。

---

## 六、上线前遗留事项（v1.0.0 归档时状态）

> 以下为结项归档时尚未闭环的事项，均已完成代码/脚本交付，待具备环境后验证：

- [ ] **容器全栈冒烟**：本机无 Docker Desktop，`docker-compose up -d --build` 端到端启动、
      `bash scripts/smoke_test.sh` 冒烟、MySQL initdb 初始化实测未执行。
      补做方式：安装 Docker → 填 `.env` 必填项（见 §一）→ `docker compose up -d --build` → 冒烟全绿即闭环
- [ ] **真实微信支付/退款**：当前为模拟支付。接通需商户号资质，切换点已在
      `OrderServiceImpl.payment()` 注释标注
- [ ] **WebSocket 握手鉴权**：来单提醒通道未校验 token，上线前必须补拦截器
- [ ] **生产 profile 收敛**：确认 prod 下关闭 Knife4j (`springdoc.api-docs.enabled=false`)、
      Actuator `show-details` 收紧并独立 management 端口
- [ ] **向量库同步任务**：教练资料/价格变更后需触发 Milvus upsert（当前为手动）
- [ ] **备份恢复演练**：`backup_mysql.sh` 已交付但未实跑 restore 验证
