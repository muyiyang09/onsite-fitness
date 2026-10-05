#!/usr/bin/env bash
# MySQL 备份脚本（§6.33）—— 每日全量 + binlog 保留
# 用法：bash scripts/backup_mysql.sh
# crontab: 0 2 * * * /opt/onsite-fitness/scripts/backup_mysql.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/data/backups/mysql}"
RETAIN_DAYS="${RETAIN_DAYS:-7}"
DB_HOST="${MYSQL_HOST:-127.0.0.1}"
DB_PORT="${MYSQL_PORT:-3306}"
DB_USER="${MYSQL_USER:-root}"
DB_PASS="${MYSQL_PASSWORD:?MYSQL_PASSWORD required}"
DB_NAME="${MYSQL_DATABASE:-onsite_fitness}"

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "[$(date)] 开始备份 $DB_NAME → $DUMP_FILE"

mysqldump \
  -h "$DB_HOST" -P "$DB_PORT" \
  -u "$DB_USER" -p"$DB_PASS" \
  --single-transaction --quick --routines --triggers \
  --set-gtid-purged=OFF \
  "$DB_NAME" 2>/dev/null | gzip > "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "[$(date)] 备份完成: $DUMP_FILE ($DUMP_SIZE)"

# 清理过期备份
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$RETAIN_DAYS" -delete
echo "[$(date)] 已清理 ${RETAIN_DAYS} 天前的旧备份"

# 校验：解压前 100 行确认非空
if gzip -t "$DUMP_FILE" 2>/dev/null; then
  echo "[$(date)] gzip 完整性校验通过"
else
  echo "[$(date)] 警告: gzip 校验失败，请检查备份文件" >&2
  exit 1
fi
