"""kk-mis 企业管理 + 财务 主应用"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import close_db, init_db
from .routes import all_routers

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kk-mis-admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("kk-mis Admin 启动中...")
    logger.info(f"  - 监听: {settings.host}:{settings.port}")
    logger.info(f"  - 数据库: {settings.database_display}")
    logger.info(f"  - JWT: {settings.jwt_algorithm} access={settings.access_token_expire}s")
    logger.info("=" * 60)
    try:
        await init_db()
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    yield
    await close_db()
    logger.info("kk-mis Admin 关闭")


app = FastAPI(
    title="kk-mis Admin API",
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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "admin",
        "version": "0.1.0",
        "database": settings.database_display,
    }


@app.get("/")
async def root():
    return {"name": "kk-mis Admin", "version": "0.1.0", "docs": "/docs"}
