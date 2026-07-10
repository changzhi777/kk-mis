"""kk-mis 会议纪要主应用入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import close_db, init_db
from .routes.meetings import router as meetings_router
from .schemas import HealthResponse

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kk-mis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动
    logger.info("=" * 60)
    logger.info("kk-mis 会议纪要主应用启动中...")
    logger.info(f"  - 监听: {settings.host}:{settings.port}")
    logger.info(f"  - 数据库: {settings.database_display}")
    logger.info(f"  - LLM: {settings.glm_model} (GLM)")
    logger.info(f"  - ASR Cluster: {settings.asr_cluster_url}")
    logger.info("=" * 60)
    try:
        await init_db()
    except Exception as e:
        logger.error(f"DB init failed: {e}")
        # 不阻塞服务启动，可以后续重试
    yield
    # 关闭
    await close_db()
    logger.info("kk-mis 关闭")


app = FastAPI(
    title="kk-mis Meeting Notes API",
    description="MIS 管理系统 - 会议纪要 AI 整理服务",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
_cors_list = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# 注册路由
app.include_router(meetings_router)


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    # 检查 ASR 节点
    asr_nodes_count = 1  # 默认节点
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.default_asr_node_url}/health")
            if resp.status_code != 200:
                asr_nodes_count = 0
    except Exception:
        asr_nodes_count = 0

    return HealthResponse(
        status="ok",
        version="0.1.0",
        asr_nodes=asr_nodes_count,
        llm_provider=f"glm:{settings.glm_model} | minimax:{settings.minimax_model} | omlx({settings.omlx_model})",
        database=settings.database_display,
    )


@app.get("/llm/providers")
async def llm_providers():
    """列出所有可用的 LLM 提供商"""
    from .services.llm import list_providers
    return {"providers": list_providers()}


@app.get("/")
async def root():
    return {
        "name": "kk-mis Meeting Notes",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )