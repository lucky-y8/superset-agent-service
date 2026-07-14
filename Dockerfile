# Build a small production image with the same Python version used in development.
# 使用与开发环境一致的 Python 版本构建精简生产镜像；基础镜像可切换到私有仓库。
ARG PYTHON_BASE_IMAGE=python:3.13-slim
FROM ${PYTHON_BASE_IMAGE}

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Build tools are needed only while installing packages that lack binary wheels.
# 构建工具仅用于安装没有预编译 wheel 的 Python 依赖，安装完成后立即删除。
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && python -m venv /app/.venv

COPY requirements.txt ./
RUN pip install --index-url "${PIP_INDEX_URL}" --upgrade pip \
    && pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY alembic.ini ./
COPY alembic ./alembic
COPY superset_agent_service ./superset_agent_service
COPY docker/entrypoint.sh /usr/local/bin/agent-entrypoint

# The service never needs root privileges at runtime.
# 服务运行时不需要 root 权限，降低容器被利用后的影响范围。
RUN chmod +x /usr/local/bin/agent-entrypoint \
    && useradd --create-home --uid 10001 agent \
    && chown -R agent:agent /app

USER agent

EXPOSE 9003

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:9003/api/v1/health || exit 1

ENTRYPOINT ["agent-entrypoint"]
