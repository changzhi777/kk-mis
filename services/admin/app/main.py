"""kk-cms 企业管理 + 财务 主应用"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request

from . import cache
from .config import settings
from .db import close_db, init_db
from .routes import all_routers

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kk-cms-admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("kk-cms Admin 启动中...")
    logger.info(f"  - 监听: {settings.host}:{settings.port}")
    logger.info(f"  - 数据库: {settings.database_display}")
    logger.info(f"  - JWT: {settings.jwt_algorithm} access={settings.access_token_expire}s")
    logger.info("=" * 60)
    try:
        await init_db()
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    await cache.init()  # Redis 缓存层（fail-open，失败不影响启动）
    # 发卡重试 poller（P0 Day 2：扫描 WebhookRetry 到期任务兜底发卡）
    from .services.payment_fulfillment import start_retry_poller
    poller_task = asyncio.create_task(start_retry_poller())
    yield
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    await cache.close()
    await close_db()
    logger.info("kk-cms Admin 关闭")


app = FastAPI(
    title="kk-cms Admin API",
    description="企业管理（RBAC）+ 财务统计",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
_cors_list = (
    ["*"]
    if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 注册路由（统一 /admin 前缀，便于 nginx 与会议纪要 /api 分流）
for _r in all_routers:
    app.include_router(_r, prefix="/admin")


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """审计中间件：记录写操作（POST/PUT/PATCH/DELETE）

    MEDIUM 修复（2026-07-16）：
    - 补 PATCH（原漏）
    - 真实 IP 取 X-Forwarded-For（反代后 request.client.host 全是 nginx IP）
    """
    start = time.time()
    response = await call_next(request)
    path = request.url.path
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and "/api/v1/" in path
        and "/auth/" not in path  # auth 操作不记日志（含密码等敏感字段）
    ):
        try:
            from .db import SessionLocal
            from .models import AuditLog
            from .security import decode_token

            user_id = None
            auth = request.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                payload = decode_token(auth.split(" ", 1)[1])
                if payload:
                    user_id = int(payload["sub"])
            # 真实 IP：优先 X-Forwarded-For（反代场景），否则回退连接 IP
            xff = request.headers.get("x-forwarded-for", "")
            ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
            async with SessionLocal() as s:
                s.add(
                    AuditLog(
                        user_id=user_id,
                        method=request.method,
                        path=path,
                        status_code=response.status_code,
                        ip=ip,
                        duration_ms=int((time.time() - start) * 1000),
                    )
                )
                await s.commit()
        except Exception as e:
            logger.warning(f"audit log failed: {e}")
    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "admin",
        "version": "0.1.0",
        "database": settings.database_display,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点（含 cos_requests_total / cos_errors_total / cos_duration_seconds）。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {"name": "kk-cms Admin", "version": "0.1.0", "docs": "/docs"}
