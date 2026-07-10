"""数据库连接管理"""
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from .config import settings
from .models import Base

logger = logging.getLogger(__name__)

# 创建异步引擎
engine = None
SessionLocal: Optional[async_sessionmaker] = None


async def init_db():
    """初始化数据库（创建表）"""
    global engine, SessionLocal
    if engine is None:
        engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
        )
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    # 创建表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"DB initialized: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")


async def close_db():
    global engine
    if engine:
        await engine.dispose()
        engine = None
        logger.info("DB closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入）"""
    if SessionLocal is None:
        await init_db()
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()