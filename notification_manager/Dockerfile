# 多阶段构建 - 支持 amd64, arm64, arm/v7
# Stage 1: 构建阶段
FROM python:3.12-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: 运行阶段
FROM python:3.12-slim as runtime

# 构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=latest

# 镜像标签
LABEL org.opencontainers.image.title="智能通知管理中台" \
      org.opencontainers.image.description="企业级通知管理平台，支持多平台统一管理" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="gwozai" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/gwozai/githubworkflow"

# 创建非root用户
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY --chown=appuser:appgroup . .

# 创建必要的目录
RUN mkdir -p logs instance && \
    chown -R appuser:appgroup /app

# 设置环境变量
ENV FLASK_APP=app.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 切换到非root用户
USER appuser

# 暴露端口
EXPOSE 5555

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5555/')" || exit 1

# 启动命令
CMD ["python", "app.py"]
