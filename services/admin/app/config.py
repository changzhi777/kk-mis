"""企业管理服务 - 配置。

安全：占位符 secret 在生产模式（APP_ENV=production 或 DB_DRIVER=postgres）
下会 fail-fast 阻止启动。

注意：不用 pydantic-settings（其 model_post_init 在 import 时冻结 env，
后续 monkeypatch 不生效）。改用手动从 os.environ 读取，每次构造都重新读。
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, model_validator


# ── 占位符检测（防硬编码 secret 被带进生产） ──────────────────────────
_PLACEHOLDER_SECRETS = frozenset(
    {
        "kk-cms-admin-secret-change-me",
        "kk-cms-jwt-secret-change-in-prod",
        "kk-cms-dev-secret-change-me",
        "change-me",
        "changeme",
        "",
    }
)

_PLACEHOLDER_PASSWORDS = frozenset(
    {
        "admin",
        "admin123",
        "admin1234",
        "password",
        "123456",
        "",
    }
)


def _env(key: str, default: str = "") -> str:
    """从 os.environ 读（每次调用重读，不冻结）。"""
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    return _env(key, str(default)).lower() == "true"


class Settings(BaseModel):
    """企业管理 + 财务服务配置（每次构造都从 os.environ 重读）"""

    # 服务
    host: str = ""
    port: int = 0
    debug: bool = False
    secret_key: str = ""
    app_env: str = ""

    # 数据库
    db_driver: str = ""
    postgres_host: str = ""
    postgres_port: int = 0
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""
    sqlite_path: str = ""

    # Redis
    redis_host: str = ""
    redis_port: int = 0
    redis_password: str = ""
    redis_db: int = 0

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = ""
    access_token_expire: int = 0
    refresh_token_expire: int = 0

    # 初始超管
    init_admin_username: str = ""
    init_admin_password: str = ""

    # OAuth
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = ""
    wechat_client_id: str = ""
    wechat_client_secret: str = ""
    wechat_redirect_uri: str = ""
    oauth_frontend_redirect: str = ""

    # CORS
    cors_origins: str = ""

    # ── Storage 抽象层（2026-07-14 Sprint 0 引入，Phase 0 仍走 local） ──
    storage_backend: str = ""        # 'local' | 'cos'
    storage_local_root: str = ""     # local 模式文件存储根目录

    # COS（Tencent Cloud 对象存储）— Phase 1 实装才生效
    cos_region: str = ""             # e.g. 'ap-guangzhou'
    cos_secret_id: str = ""          # CAM 子账号 SecretId（推荐 STS 临时凭证）
    cos_secret_key: str = ""         # CAM 子账号 SecretKey
    cos_bucket: str = ""             # e.g. 'szdhts-prod-1300000000'
    cos_appid: str = ""              # bucket 已含 appid 可留空
    cos_scheme: str = ""             # 'https' | 'http'，默认 https
    cos_cdn_domain: str = ""         # 加速域名；留空走源站
    cos_presign_expire: int = 0      # 上传 URL 有效期（秒）
    cos_download_expire: int = 0     # 下载 URL 有效期（秒）
    cos_max_object_mb: int = 0       # 单对象最大字节（MB）

    # 日志
    log_level: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        """工厂方法：每次调用都从 os.environ 重读最新值。"""
        return cls(
            host=_env("APP_HOST", "0.0.0.0"),
            port=_env_int("APP_PORT", 8300),
            debug=_env_bool("APP_DEBUG"),
            secret_key=_env("APP_SECRET_KEY", "kk-cms-admin-secret-change-me"),
            app_env=_env("APP_ENV", "development"),
            db_driver=_env("DB_DRIVER", "sqlite"),
            postgres_host=_env("POSTGRES_HOST", "127.0.0.1"),
            postgres_port=_env_int("POSTGRES_PORT", 5432),
            postgres_user=_env("POSTGRES_USER", "postgres"),
            postgres_password=_env("POSTGRES_PASSWORD", ""),
            postgres_db=_env("POSTGRES_DB", "kk_admin"),
            sqlite_path=_env("SQLITE_PATH", "./storage/admin.db"),
            redis_host=_env("REDIS_HOST", "127.0.0.1"),
            redis_port=_env_int("REDIS_PORT", 6379),
            redis_password=_env("REDIS_PASSWORD", ""),
            redis_db=_env_int("REDIS_DB", 1),
            jwt_secret=_env("JWT_SECRET", "kk-cms-jwt-secret-change-in-prod"),
            jwt_algorithm=_env("JWT_ALGORITHM", "HS256"),
            access_token_expire=_env_int("ACCESS_TOKEN_EXPIRE", 7200),
            refresh_token_expire=_env_int("REFRESH_TOKEN_EXPIRE", 604800),
            init_admin_username=_env("INIT_ADMIN_USERNAME", "admin"),
            init_admin_password=_env("INIT_ADMIN_PASSWORD", "admin123"),
            github_client_id=_env("GITHUB_CLIENT_ID", ""),
            github_client_secret=_env("GITHUB_CLIENT_SECRET", ""),
            github_redirect_uri=_env("GITHUB_REDIRECT_URI", ""),
            wechat_client_id=_env("WECHAT_CLIENT_ID", ""),
            wechat_client_secret=_env("WECHAT_CLIENT_SECRET", ""),
            wechat_redirect_uri=_env("WECHAT_REDIRECT_URI", ""),
            oauth_frontend_redirect=_env("OAUTH_FRONTEND_REDIRECT", "/oa/oauth/callback"),
            cors_origins=_env("CORS_ORIGINS", "*"),
            # ── Storage / COS ──
            storage_backend=_env("STORAGE_BACKEND", "local"),
            storage_local_root=_env("STORAGE_LOCAL_ROOT", "storage/uploads"),
            cos_region=_env("COS_REGION", ""),
            cos_secret_id=_env("COS_SECRET_ID", ""),
            cos_secret_key=_env("COS_SECRET_KEY", ""),
            cos_bucket=_env("COS_BUCKET", ""),
            cos_appid=_env("COS_APPID", ""),
            cos_scheme=_env("COS_SCHEME", "https"),
            cos_cdn_domain=_env("COS_CDN_DOMAIN", ""),
            cos_presign_expire=_env_int("COS_PRESIGN_EXPIRE", 3600),
            cos_download_expire=_env_int("COS_DOWNLOAD_EXPIRE", 600),
            cos_max_object_mb=_env_int("COS_MAX_OBJECT_MB", 500),
            log_level=_env("LOG_LEVEL", "INFO"),
        )

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """生产模式（APP_ENV=production 或 DB_DRIVER=postgres）下强制要求 secret 非占位符。"""
        is_prod = self.app_env == "production" or self.db_driver == "postgres"
        if not is_prod:
            return self

        errors: list[str] = []
        if self.jwt_secret in _PLACEHOLDER_SECRETS:
            errors.append(
                "JWT_SECRET 是占位符（生产必须改）— 设置环境变量覆盖，例如 `JWT_SECRET=$(openssl rand -hex 32)`"
            )
        if self.secret_key in _PLACEHOLDER_SECRETS:
            errors.append("APP_SECRET_KEY 是占位符")
        if self.init_admin_password in _PLACEHOLDER_PASSWORDS:
            errors.append(
                "INIT_ADMIN_PASSWORD 是占位符（生产必须改）— 当前值: "
                f"'{self.init_admin_password}'"
            )
        if self.db_driver == "postgres" and not self.postgres_password:
            errors.append("DB_DRIVER=postgres 但 POSTGRES_PASSWORD 为空")
        if errors:
            raise ValueError(
                "生产模式配置不安全，启动拒绝：\n  - " + "\n  - ".join(errors)
            )
        return self

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


settings = Settings.from_env()
Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
