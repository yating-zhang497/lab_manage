#!/bin/bash
# 研究组信息管理系统 —— 服务器端部署/更新脚本（模板，幂等，可重复执行）
#
# 用法（在服务器上执行）: bash scripts/deploy_server.sh
#
# 通过环境变量配置（未设置则使用默认值）：
#   APP_DIR=/opt/lab_manage          应用根目录
#   PYTHON_BIN=/usr/bin/python3      Python 解释器路径
#   SERVICE_NAME=lab_manage          systemd 服务名
set -e

APP_DIR="${APP_DIR:-/opt/lab_manage}"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
SERVICE_NAME="${SERVICE_NAME:-lab_manage}"

echo "[1/8] 检查 Python 依赖..."
$PYTHON_BIN -m pip install -q -r "$APP_DIR/backend/requirements.txt"

echo "[2/8] 确保管理员账号存在（已存在则跳过）..."
cd "$APP_DIR/backend"
$PYTHON_BIN -m app.create_admin

echo "[3/8] 停止服务..."
if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
  systemctl stop "$SERVICE_NAME" || true
fi

echo "[4/8] 清理 app/ 根目录孤儿文件（scp -r 只增不删，旧结构遗留需手动清理）..."
# 规则：凡 routers/<x>.py 存在且 app/<x>.py 也存在（x != __init__），删掉根目录那份
for f in "$APP_DIR/backend/app/routers/"*.py; do
  base=$(basename "$f")
  if [ "$base" = "__init__.py" ]; then continue; fi
  if [ -f "$APP_DIR/backend/app/$base" ]; then
    rm -f "$APP_DIR/backend/app/$base"
    echo "  删除孤儿: app/$base"
  fi
done

echo "[5/8] 备份数据库..."
if [ -f "$APP_DIR/backend/runtime/im.db" ]; then
  mkdir -p "$APP_DIR/backend/runtime/backups"
  cp "$APP_DIR/backend/runtime/im.db" "$APP_DIR/backend/runtime/backups/im.db.$(date +%Y%m%d%H%M%S)"
fi

echo "[6/8] 数据迁移（幂等，新装为 no-op）..."
$PYTHON_BIN -m scripts.migrate_funding_snapshots || true

echo "[7/8] 注册并重启服务..."
if [ ! -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
  cp "$APP_DIR/scripts/im.service" "/etc/systemd/system/${SERVICE_NAME}.service"
fi
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 3

echo "[8/8] 服务状态..."
systemctl is-active "$SERVICE_NAME"

echo "健康检查..."
curl -s http://127.0.0.1:8000/api/health
echo
echo "部署完成。"
