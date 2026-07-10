"""数据库连接管理"""
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings
from .models import Base

logger = logging.getLogger(__name__)

engine = None
SessionLocal: Optional[async_sessionmaker] = None


async def init_db():
    """初始化数据库（建表 + 初始超管/菜单）"""
    global engine, SessionLocal
    if engine is None:
        if settings.db_driver == "sqlite":
            engine = create_async_engine(
                settings.database_url,
                echo=settings.debug,
                connect_args={"check_same_thread": False},
            )
        else:
            engine = create_async_engine(
                settings.database_url,
                echo=settings.debug,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
            )
        SessionLocal = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"DB initialized: {settings.database_display}")

    # 初始数据（超管 + 默认菜单/权限 + 默认财务科目）
    from .seed import seed_initial_data
    await seed_initial_data()


async def close_db():
    global engine
    if engine:
        await engine.dispose()
        engine = None
        logger.info("DB closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if SessionLocal is None:
        await init_db()
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
