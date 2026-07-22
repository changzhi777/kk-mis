"""V2.0 实名认证（M2.6：三要素 API，注册即实名）

客户扫推广码注册后即实名（V2.0 业务要求）；id_card_no 不落明文，仅存 SHA256 hash。
M2.6 stub：直接通过（真三要素 API 需对接公安二要素/三要素服务商，留接入）。
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import User
from ...schemas.v2.realname import V2RealnameStatus, V2RealnameVerify

router = APIRouter(prefix="/api/v2/realname", tags=["v2-realname"])


def _hash_id_card(id_card_no: str) -> str:
    """SHA256 hash 身份证号（不存明文）。"""
    return hashlib.sha256(id_card_no.strip().encode()).hexdigest()


def _mask_id_card(id_card_no: str) -> str:
    """脱敏展示（保留首 3 末 4，中间打星）。"""
    s = id_card_no.strip()
    if len(s) <= 7:
        return "*" * len(s)
    return f"{s[:3]}{'*' * (len(s) - 7)}{s[-4:]}"


@router.post("/verify", response_model=V2RealnameStatus)
async def verify_realname(
    req: V2RealnameVerify,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交实名认证（三要素：姓名 + 身份证号）。

    M2.6 stub：直接通过（真三要素 API 待对接公安二/三要素服务商）。
    已实名用户再次提交 → 409（防覆盖；变更需联系平台）。
    """
    if user.realname_status == "verified":
        raise HTTPException(409, "已实名认证，如需变更请联系平台")
    # TODO M2.6+：对接真三要素 API（姓名+身份证号+手机号 校验）
    user.real_name = req.real_name.strip()
    user.id_card_hash = _hash_id_card(req.id_card_no)
    user.realname_status = "verified"
    await session.commit()
    await session.refresh(user)
    return V2RealnameStatus(
        realname_status=user.realname_status,
        real_name=user.real_name,
        id_card_masked=_mask_id_card(req.id_card_no),
    )


@router.get("/me", response_model=V2RealnameStatus)
async def get_my_realname(
    user: User = Depends(get_current_user),
):
    """查自己实名状态（脱敏展示身份证）。"""
    return V2RealnameStatus(
        realname_status=user.realname_status,
        real_name=user.real_name,
        id_card_masked=None,  # 不回显完整身份证；verified 用户可查脱敏（需原号，此处略）
    )
