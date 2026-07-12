"""企业管理服务 - 配置"""
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """企业管理 + 财务服务配置"""

    # 服务
    host: str = os.getenv("APP_HOST", "0.0.0.0")
    port: int = int(os.getenv("APP_PORT", "8300"))
    debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("APP_SECRET_KEY", "kk-mis-admin-secret-change-me")

    # 数据库（默认 SQLite 便于开发；生产用 PostgreSQL）
    db_driver: str = os.getenv("DB_DRIVER", "sqlite")
    postgres_host: str = os.getenv("POSTGRES_HOST", "127.0.0.1")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")
    postgres_db: str = os.getenv("POSTGRES_DB", "kk_admin")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./storage/admin.db")

    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")
    redis_db: int = int(os.getenv("REDIS_DB", "1"))

    # JWT 认证
    jwt_secret: str = os.getenv("JWT_SECRET", "kk-mis-jwt-secret-change-in-prod")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    # access token 2 小时，refresh token 7 天
    access_token_expire: int = int(os.getenv("ACCESS_TOKEN_EXPIRE", "7200"))
    refresh_token_expire: int = int(os.getenv("REFRESH_TOKEN_EXPIRE", "604800"))

    # 初始超管（首次启动 init_db 时写入）
    init_admin_username: str = os.getenv("INIT_ADMIN_USERNAME", "admin")
    init_admin_password: str = os.getenv("INIT_ADMIN_PASSWORD", "admin123")

    # OAuth 第三方登录（GitHub 先打通，微信预留）
    github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
    github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    github_redirect_uri: str = os.getenv("GITHUB_REDIRECT_URI", "")
    wechat_client_id: str = os.getenv("WECHAT_CLIENT_ID", "")
    wechat_client_secret: str = os.getenv("WECHAT_CLIENT_SECRET", "")
    wechat_redirect_uri: str = os.getenv("WECHAT_REDIRECT_URI", "")
    oauth_frontend_redirect: str = os.getenv("OAUTH_FRONTEND_REDIRECT", "/oa/oauth/callback")

    # CORS
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    # 日志
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        if self.db_driver == "sqlite":
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_display(self) -> str:
        if self.db_driver == "sqlite":
            return f"sqlite://{self.sqlite_path}"
        return f"postgresql://{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
