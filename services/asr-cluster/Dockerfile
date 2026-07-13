# ASR Cluster Manager — 多 MLX 节点 ASR 集群管理 (:9100)
# KISS: 单阶段 slim 镜像，无冗余层
FROM python:3.12-slim

# 容器内时区与日志（与生产对齐 CST）
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 依赖分层（利用 Docker 层缓存）
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 应用代码
COPY app/ ./app/

# 健康检查（cluster 自身健康，无外部依赖）
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://127.0.0.1:9100/health', timeout=3); r.raise_for_status()" || exit 1

EXPOSE 9100

# 启动（uvicorn 标准参数，supervisord 不需要 — 单进程足够）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9100", "--log-level", "info"]