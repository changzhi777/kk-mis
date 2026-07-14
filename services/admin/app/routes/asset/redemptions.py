"""卡券核销（scan 扫码 / manual 手动 / batch 批量 / self 自助验密码 / dynamic 动态码 V1）"""
from ...utils import utcnow
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
from ...services.dynamic_code import generate as gen_dynamic, verify as verify_dynamic

router = APIRouter(prefix="/api/v1/asset/redemptions", tags=["asset-redemption"])


async def _redeem_one(card_no: str, method: str, password, remark, user: User, session: AsyncSession) -> dict:
    card = (
        await session.execute(select(AssetCard).where(AssetCard.card_no == card_no))
    ).scalar_one_or_none()
    if not card:
        return {"card_no": card_no, "ok": False, "error": "卡券不存在"}
    if card.status != "issued":
        return {"card_no": card_no, "ok": False, "error": f"状态 {card.status} 不可核销"}
    if card.valid_until and card.valid_until < utcnow():
        card.status = "expired"
        return {"card_no": card_no, "ok": False, "error": "已过期"}
    # self 自助核销必须验密码
    if method == "self":
        if not password or not verify_password(password, card.password_hash):
            return {"card_no": card_no, "ok": False, "error": "密码错误"}
    # V4 核销限次：redeemed_count++，达 max_redeem_count 才置 used（NULL/1=一次性）
    card.redeemed_count = (card.redeemed_count or 0) + 1
    max_cnt = card.max_redeem_count if card.max_redeem_count is not None else 1
    if card.redeemed_count >= max_cnt:
        card.status = "used"
        card.used_at = utcnow()
    r = AssetRedemption(
        card_id=card.id, redeemer_id=user.id, method=method,
        amount=card.face_value, remark=remark,
    )
    session.add(r)
    # V2 核销给持卡人加分（1 元 = 1 分）+ 累计消费
    if card.holder_user_id and card.face_value:
        from ...services.points import add_consumed, award_points
        pts = int(card.face_value)
        if pts > 0:
            await award_points(card.holder_user_id, pts, "redeem", session, ref_type="card", ref_id=card.id)
            await add_consumed(card.holder_user_id, card.face_value, session)
            # V3 等级自动升级（累计消费达门槛）
            from ...services.member_level import check_and_upgrade_level
            await check_and_upgrade_level(session, card.holder_user_id)
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


@router.post("/generate-dynamic")
async def generate_dynamic_code(
    card_id: int = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """V1 持卡人生成动态核销码（30s 有效，防截图/重放）。校验卡归属。"""
    card = await session.get(AssetCard, card_id)
    if not card:
        raise HTTPException(404, "卡券不存在")
    # 仅持卡人或 admin 可生成
    if card.holder_user_id != user.id and user.username != "admin":
        raise HTTPException(403, "无权生成此卡的动态码")
    if card.status != "issued":
        raise HTTPException(400, f"状态 {card.status} 不可核销")
    return gen_dynamic(card_id)


@router.post("/redeem-dynamic")
async def redeem_dynamic(
    code: str = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """V1 商家扫动态码核销：验签 + 时效 + nonce 防重放 → 核销。"""
    try:
        payload = await verify_dynamic(code)
    except ValueError as e:
        raise HTTPException(400, str(e))
    card = await session.get(AssetCard, payload["card_id"])
    if not card:
        raise HTTPException(404, "卡券不存在")
    result = await _redeem_one(card.card_no, "scan", None, "动态码核销", user, session)
    await session.commit()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/transfer-card")
async def transfer_card(
    card_id: int = Body(..., embed=True),
    to_user_id: int = Body(..., embed=True),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """V5 卡券转赠：持卡人 → 目标用户（转持有 + 记 card_transfer）。"""
    from ...models import CardTransfer

    card = await session.get(AssetCard, card_id)
    if not card:
        raise HTTPException(404, "卡券不存在")
    if card.holder_user_id != user.id and user.username != "admin":
        raise HTTPException(403, "无权转赠此卡")
    if card.status != "issued":
        raise HTTPException(400, f"状态 {card.status} 不可转赠")
    to_user = await session.get(User, to_user_id)
    if not to_user:
        raise HTTPException(404, "目标用户不存在")
    from_uid = card.holder_user_id
    card.holder_user_id = to_user_id  # 转持有
    session.add(
        CardTransfer(
            card_id=card_id, from_user_id=from_uid, to_user_id=to_user_id,
            status="completed",
        )
    )
    await session.commit()
    return {"success": True, "card_id": card_id, "from": from_uid, "to": to_user_id}


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
