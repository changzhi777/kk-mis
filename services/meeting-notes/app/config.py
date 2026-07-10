"""会议纪要主应用 - 配置"""
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """主应用配置"""

    # 服务
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("APP_SECRET_KEY", "kk-mis-dev-secret-change-me")

    # 数据库（默认 SQLite，便于开发；生产用 PostgreSQL）
    db_driver: str = os.getenv("DB_DRIVER", "sqlite")
    postgres_host: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")
    postgres_db: str = os.getenv("POSTGRES_DB", "kk_mis")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./storage/kk_mis.db")

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "0"))

    # GLM LLM
    glm_api_key: str = os.getenv("GLM_API_KEY", "")
    glm_base_url: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    glm_model: str = os.getenv("GLM_MODEL", "glm-4-plus")

    # minimax LLM（备用）
    minimax_api_key: str = os.getenv("MINIMAX_API_KEY", "")
    minimax_base_url: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    minimax_model: str = os.getenv("MINIMAX_MODEL", "MiniMax-Text-01")

    # oMLX 本地 LLM（OpenAI 兼容协议，跑 MLX 格式模型）
    omlx_enabled: bool = os.getenv("OMLX_ENABLED", "true").lower() == "true"
    omlx_base_url: str = os.getenv("OMLX_BASE_URL", "http://localhost:8008/v1")
    omlx_api_key: str = os.getenv("OMLX_API_KEY", "ak47")
    omlx_model: str = os.getenv("OMLX_MODEL", "gemma-4-e4b-it-4bit")

    # ASR Cluster
    asr_cluster_url: str = os.getenv("ASR_CLUSTER_URL", "http://localhost:9100")
    default_asr_node_url: str = os.getenv(
        "DEFAULT_ASR_NODE_URL", "http://100.88.88.34:9000"
    )
    mlx_asr_api_key: str = os.getenv("MLX_ASR_API_KEY", "kk-mis-asr-local-dev-key-2026")

    # 文件存储
    upload_dir: str = os.getenv("UPLOAD_DIR", "./storage/uploads")
    output_dir: str = os.getenv("OUTPUT_DIR", "./storage/outputs")
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

    # 日志
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        """数据库连接 URL（SQLite 或 PostgreSQL）"""
        if self.db_driver == "sqlite":
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL"""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
# 确保目录存在
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.output_dir).mkdir(parents=True, exist_ok=True)