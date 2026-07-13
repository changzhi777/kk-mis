"""config.py 安全校验测试。

生产模式下占位符 secret 必须被拒（fail-fast）。

注意：conftest.py 在 module 级别设了 JWT_SECRET="test-secret" 等占位符，
用 monkeypatch.setenv 会被覆盖（module-level env 优先级更高）。
所以这里直接改 os.environ + 立即读 + 用 monkeypatch.delenv 清掉 conftest 的设置。
"""

from __future__ import annotations

import os

import pytest


def _build_settings(monkeypatch, **overrides):
    """清掉 conftest 设的 env + 应用 overrides + 构造 Settings。

    直接改 os.environ（不依赖 monkeypatch fixture 顺序）。
    monkeypatch 仍用于测试结束时自动还原。
    """
    import os

    # 清掉 conftest 模块级别设的占位符
    for k in [
        "APP_ENV",
        "JWT_SECRET",
        "APP_SECRET_KEY",
        "INIT_ADMIN_PASSWORD",
        "DB_DRIVER",
        "POSTGRES_PASSWORD",
    ]:
        monkeypatch.delenv(k, raising=False)
        os.environ.pop(k, None)
    for k, v in overrides.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
            os.environ.pop(k, None)
        else:
            monkeypatch.setenv(k, v)
            os.environ[k] = v

    from app.config import Settings

    return Settings.from_env()


def test_dev_mode_with_placeholders_allowed(monkeypatch):
    """开发模式允许占位符（dev 起步）"""
    import os

    s = _build_settings(
        monkeypatch,
        APP_ENV="development",
        JWT_SECRET="kk-mis-jwt-secret-change-in-prod",
        APP_SECRET_KEY="kk-mis-admin-secret-change-me",
        DB_DRIVER="sqlite",
        INIT_ADMIN_PASSWORD="admin123",
    )
    print(f"DEBUG: env JWT_SECRET = {os.getenv('JWT_SECRET', 'NONE')[:30]}")
    print(f"DEBUG: settings.jwt_secret = {s.jwt_secret[:30]}")
    assert s.jwt_secret == "kk-mis-jwt-secret-change-in-prod"


def test_production_mode_rejects_placeholder_jwt(monkeypatch):
    """生产模式 + 占位符 JWT_SECRET → fail-fast"""
    with pytest.raises(Exception) as exc:
        _build_settings(
            monkeypatch,
            APP_ENV="production",
            JWT_SECRET="kk-mis-jwt-secret-change-in-prod",
            APP_SECRET_KEY="real-app-secret-xyz",
            DB_DRIVER="sqlite",
            INIT_ADMIN_PASSWORD="StrongP@ss123!",
        )
    msg = str(exc.value)
    assert "JWT_SECRET" in msg or "占位符" in msg


def test_production_mode_rejects_placeholder_admin_password(monkeypatch):
    """生产模式 + 占位符 admin 密码 → fail-fast"""
    with pytest.raises(Exception) as exc:
        _build_settings(
            monkeypatch,
            APP_ENV="production",
            JWT_SECRET="real-secret-1234567890",
            APP_SECRET_KEY="real-app-secret-xyz",
            DB_DRIVER="sqlite",
            INIT_ADMIN_PASSWORD="admin",
        )
    assert "INIT_ADMIN_PASSWORD" in str(exc.value)


def test_postgres_mode_rejects_empty_password(monkeypatch):
    """DB=postgres + 空 password → fail-fast"""
    with pytest.raises(Exception) as exc:
        _build_settings(
            monkeypatch,
            APP_ENV="development",
            DB_DRIVER="postgres",
            POSTGRES_PASSWORD="",
            JWT_SECRET="real-secret-1234567890",
            APP_SECRET_KEY="real-app-secret-xyz",
            INIT_ADMIN_PASSWORD="StrongP@ss123!",
        )
    assert "POSTGRES_PASSWORD" in str(exc.value)


def test_production_mode_with_real_secrets_allowed(monkeypatch):
    """生产模式 + 真 secret → 通过"""
    s = _build_settings(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="real-secret-1234567890-abcdef",
        APP_SECRET_KEY="real-app-secret-xyz",
        DB_DRIVER="sqlite",
        INIT_ADMIN_PASSWORD="StrongP@ss123!",
    )
    assert s.app_env == "production"
    assert s.jwt_secret == "real-secret-1234567890-abcdef"