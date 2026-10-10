#!/usr/bin/env bash
# ============================================================
#  上门体育 · Docker 一键启动（Linux / macOS / Git Bash）
#  用法: bash scripts/start_docker.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== 上门体育 · Docker 一键启动 ==="

# ---- 1. 检查 Docker ----
command -v docker >/dev/null 2>&1 || { echo "[ERROR] 未检测到 docker，请先安装 Docker。"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "[ERROR] 未检测到 docker compose v2。"; exit 1; }
docker info >/dev/null 2>&1 || { echo "[ERROR] Docker 守护进程未运行。"; exit 1; }

# ---- 2. 检查 .env ----
if [ ! -f .env ]; then
  echo "[WARN] 未找到 .env，已从 .env.example 复制模板。"
  cp .env.example .env
  echo "请先编辑 .env 填写必填项（MySQL/Redis/MinIO 密码、JWT/AES 密钥），然后重新运行本脚本。"
  echo "密钥生成: openssl rand -hex 32"
  exit 1
fi

# ---- 3. 校验必填变量非空（docker-compose 中标记 ?required 的项）----
MISSING=""
for V in MYSQL_ROOT_PASSWORD MYSQL_APP_PASSWORD REDIS_PASSWORD MILVUS_MINIO_ACCESS_KEY MILVUS_MINIO_SECRET_KEY; do
  grep -q "^${V}=." .env || MISSING="$MISSING $V"
done
if [ -n "$MISSING" ]; then
  echo "[ERROR] .env 中以下必填项为空:$MISSING"
  exit 1
fi

# ---- 4. 构建并启动 ----
echo ">> docker compose up -d --build"
docker compose up -d --build

# ---- 5. 等待核心服务健康（最长约 3 分钟，Milvus 首次启动较慢）----
echo ">> 等待服务就绪..."
for i in $(seq 1 36); do
  B=$(docker inspect --format '{{.State.Health.Status}}' sports-backend 2>/dev/null || echo "starting")
  A=$(docker inspect --format '{{.State.Health.Status}}' sports-ai 2>/dev/null || echo "starting")
  [ "$B" = "healthy" ] && [ "$A" = "healthy" ] && break
  sleep 5
done

# ---- 6. 打印访问入口 ----
cat <<'EOF'

=== 启动完成，访问入口 ===
  管理端前端 : http://localhost:5173
  后端 API   : http://localhost:8080
  AI 微服务  : http://localhost:18000/healthz
  Attu(Milvus): http://localhost:8001
  Grafana    : http://localhost:3000  (admin / admin)
  Prometheus : http://localhost:9090

常用命令:
  查看日志   : docker compose logs -f <服务名>
  停止服务   : docker compose down
  冒烟测试   : bash scripts/smoke_test.sh
EOF
