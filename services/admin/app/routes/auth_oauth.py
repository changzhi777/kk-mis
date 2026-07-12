"""OAuth 第三方登录路由（authorize / callback）

流程：前端跳 authorize → 后端 302 到 GitHub → 用户授权 → GitHub 回 callback
→ 验 state → 换 token → 拿 userinfo → 查/建 kk-mis 账号 → 签 JWT → 302 前端#token
"""
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..models import Role, SocialAccount, User, user_roles
from ..oauth.base import SocialUserInfo
from ..oauth.registry import get_connector
from ..security import create_access_token, create_refresh_token, hash_password

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["auth-oauth"])

_STATE_TYPE = "oauth_state"
_STATE_EXPIRE = 600  # 10 分钟


def _make_state(provider: str) -> str:
    """生成签名 state（JWT，含 provider+exp+nonce，防 CSRF）"""
    payload = {
        "sub": provider,
        "type": _STATE_TYPE,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=_STATE_EXPIRE),
        "nonce": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _verify_state(state: str, provider: str) -> bool:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return False
    return payload.get("type") == _STATE_TYPE and payload.get("sub") == provider


def _build_redirect_uri(provider: str) -> str:
    """回调地址：优先用 .env 配置（生产稳定），否则 None（connector 兜底）"""
    return {
        "github": settings.github_redirect_uri,
        "wechat": settings.wechat_redirect_uri,
    }.get(provider) or ""


@router.get("/{provider}/authorize")
async def oauth_authorize(provider: str, request: Request):
    """跳转到第三方授权页（前端 window.location 过来）"""
    try:
        connector = get_connector(provider)
    except KeyError:
        raise HTTPException(404, f"不支持的登录方式: {provider}")
    redirect_uri = _build_redirect_uri(provider) or _guess_redirect_uri(provider, request)
    state = _make_state(provider)
    try:
        url = connector.get_authorize_url(state, redirect_uri)
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    return RedirectResponse(url)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """第三方回调：验 state → 换 token → userinfo → 查建账号 → 302 前端"""
    try:
        connector = get_connector(provider)
    except KeyError:
        return _redirect_frontend(error="不支持的登录方式")
    if not _verify_state(state, provider):
        return _redirect_frontend(error="state 校验失败，请重试")
    redirect_uri = _build_redirect_uri(provider) or _guess_redirect_uri(provider, request)
    try:
        access_token = await connector.exchange_token(code, redirect_uri)
        info = await connector.get_userinfo(access_token)
    except Exception as e:
        return _redirect_frontend(error=f"授权失败: {e}")
    user = await _resolve_user(session, provider, info)
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return _redirect_frontend(token=access, refresh=refresh)


async def _resolve_user(session: AsyncSession, provider: str, info: SocialUserInfo) -> User:
    """查/建用户：① 已绑社交账号 ② 同 email 关联 ③ 新建"""
    # 1. 已绑
    sa = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.provider == provider,
                SocialAccount.provider_uid == info.provider_uid,
            )
        )
    ).scalar_one_or_none()
    if sa:
        user = await session.get(User, sa.user_id)
        if user and user.status:
            return user
    # 2. 同 email 关联现有账号
    if info.email:
        existing = (
            await session.execute(select(User).where(User.email == info.email))
        ).scalar_one_or_none()
        if existing and existing.status:
            await _bind_social(session, existing.id, provider, info)
            await session.commit()
            return existing
    # 3. 新建（username=provider_uid，随机密码）
    user = User(
        username=f"{provider}_{info.provider_uid}"[:50],
        password_hash=hash_password(secrets.token_hex(16)),
        name=info.name,
        email=info.email,
        status=True,
    )
    session.add(user)
    await session.flush()
    # 绑定 staff 角色（基础菜单权限，与注册向导一致）
    staff = (
        await session.execute(select(Role).where(Role.code == "staff"))
    ).scalar_one_or_none()
    if staff:
        await session.execute(user_roles.insert().values(user_id=user.id, role_id=staff.id))
    await _bind_social(session, user.id, provider, info)
    await session.commit()
    return user


async def _bind_social(session: AsyncSession, user_id: int, provider: str, info: SocialUserInfo):
    """绑定社交账号（已存在则跳过，由 unique 约束保证）"""
    exists = (
        await session.execute(
            select(SocialAccount).where(
                SocialAccount.provider == provider,
                SocialAccount.provider_uid == info.provider_uid,
            )
        )
    ).scalar_one_or_none()
    if exists:
        return
    session.add(
        SocialAccount(
            user_id=user_id, provider=provider,
            provider_uid=info.provider_uid, provider_name=info.name,
        )
    )
    await session.flush()


def _guess_redirect_uri(provider: str, request: Request) -> str:
    """未配置时的兜底回调地址（用请求 host 推断）"""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/v1/auth/oauth/{provider}/callback"


def _redirect_frontend(token: str = "", refresh: str = "", error: str = "") -> RedirectResponse:
    """302 到前端回调页，token 走 URL hash（不进 server log）"""
    params = {}
    if token:
        params["t"] = token
    if refresh:
        params["r"] = refresh
    if error:
        params["error"] = error
    fragment = urlencode(params)
    return RedirectResponse(f"{settings.oauth_frontend_redirect}#{fragment}")
