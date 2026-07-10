"""卡券核销（scan 扫码 / manual 手动 / batch 批量 / self 自助验密码）"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import AssetCard, AssetRedemption, User
from ...schemas.asset import RedemptionOut, RedemptionRequest
from ...security import verify_password

router = APIRouter(prefix="/api/v1/asset/redemptions", tags=["asset-redemption"])


async def _redeem_one(card_no: str, method: str, password, remark, user: User, session: AsyncSession) -> dict:
    card = (
        await session.execute(select(AssetCard).where(AssetCard.card_no == card_no))
    ).scalar_one_or_none()
    if not card:
        return {"card_no": card_no, "ok": False, "error": "卡券不存在"}
    if card.status != "issued":
        return {"card_no": card_no, "ok": False, "error": f"状态 {card.status} 不可核销"}
    if card.valid_until and card.valid_until < datetime.utcnow():
        card.status = "expired"
        return {"card_no": card_no, "ok": False, "error": "已过期"}
    # self 自助核销必须验密码
    if method == "self":
        if not password or not verify_password(password, card.password_hash):
            return {"card_no": card_no, "ok": False, "error": "密码错误"}
    card.status = "used"
    card.used_at = datetime.utcnow()
    r = AssetRedemption(
        card_id=card.id, redeemer_id=user.id, method=method,
        amount=card.face_value, remark=remark,
    )
    session.add(r)
    return {"card_no": card_no, "ok": True, "amount": float(card.face_value), "card_id": card.id}


@router.post("/redeem")
async def redeem(
    req: RedemptionRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """单张核销（scan/manual/self）"""
    result = await _redeem_one(req.card_no, req.method, req.password, req.remark, user, session)
    await session.commit()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/redeem-batch")
async def redeem_batch(
    card_nos: List[str] = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """批量核销"""
    results = []
    for no in card_nos:
        results.append(await _redeem_one(no, "batch", None, "批量核销", user, session))
    await session.commit()
    ok = sum(1 for r in results if r["ok"])
    return {"results": results, "success": ok, "failed": len(results) - ok}


@router.get("")
async def list_redemptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    stmt = select(AssetRedemption).order_by(AssetRedemption.id.desc())
    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    items = (
        await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    return {
        "items": [RedemptionOut.model_validate(r).model_dump() for r in items],
        "total": total, "page": page, "page_size": page_size,
    }
