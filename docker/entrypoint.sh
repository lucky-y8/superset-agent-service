#!/bin/sh
set -eu

check_secret() {
  name="$1"
  value="$2"
  case "$value" in
    ""|CHANGE_ME*)
      echo "Refusing to start: $name is empty or still uses a CHANGE_ME placeholder." >&2
      exit 1
      ;;
  esac
}

# Refuse insecure template values without ever printing the secret itself.
# 检测空密钥和模板占位符，但绝不把真实密钥输出到日志。
check_secret "SECRET_KEY" "${SECRET_KEY:-}"
check_secret "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD:-}"
check_secret "REDIS_PASSWORD" "${REDIS_PASSWORD:-}"
check_secret "QDRANT_API_KEY" "${QDRANT_API_KEY:-}"
check_secret "SUPERSET_AGENT_SERVICE_KEY" "${SUPERSET_AGENT_SERVICE_KEY:-}"
check_secret "OPENAI_API_KEY" "${OPENAI_API_KEY:-}"

if [ "${RAG_ENABLED:-false}" = "true" ]; then
  check_secret "DASHSCOPE_API_KEY" "${DASHSCOPE_API_KEY:-}"
  check_secret "OSS_ACCESS_KEY_ID" "${OSS_ACCESS_KEY_ID:-}"
  check_secret "OSS_ACCESS_KEY_SECRET" "${OSS_ACCESS_KEY_SECRET:-}"
fi

# Apply schema changes once the PostgreSQL health check has succeeded.
# PostgreSQL 健康检查通过后执行数据库迁移，确保应用和表结构版本一致。
python -m alembic upgrade head

# Replace the shell process so Docker signals reach Uvicorn directly.
# 使用 exec 替换 shell 进程，让 Docker 停止信号能够直接传递给 Uvicorn。
exec uvicorn superset_agent_service.main:app \
  --host 0.0.0.0 \
  --port "${SERVER_PORT:-9003}" \
  --workers "${UVICORN_WORKERS:-2}" \
  --proxy-headers \
  --forwarded-allow-ips="*"
