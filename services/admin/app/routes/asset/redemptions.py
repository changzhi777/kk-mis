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
    # FOR UPDATE 行锁：串行化对同一张卡的并发核销，防止一次性卡
    # （max_redeem_count=1）被两个并发请求各自通过 status=="issued" 检查后
    # 各自 redeemed_count+=1 造成超核。PG 走 SELECT...FOR UPDATE；
    # SQLite 由 SQLAlchemy 静默降级为普通 SELECT（开发环境无并发）。
    card = (
        await session.execute(
            select(AssetCard).where(AssetCard.card_no == card_no).with_for_update()
        )
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
            # V3 等级自动升级由 add_consumed 内部 upgrade_level 触发（points.py，去重 member_level）
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
    """V5 卡券转赠（H15：两步确认状态机）。

    第 1 步：持卡人发起转赠，仅创建 CardTransfer(status="pending")，
    **不立即转 holder**——等待接收人确认（accept）或拒绝（reject）。
    超过 7 天未确认由管理端标 expired（暂不实现定时，仅留状态注释）。
    """
    from ...models import CardTransfer

    card = await session.get(AssetCard, card_id)
    if not card:
        raise HTTPException(404, "卡券不存在")
    # 权限：持卡人本人或超管（H15：不再用 username == "admin" 硬编码，改走角色判断）
    if card.holder_user_id != user.id:
        from ...deps import is_super_admin
        if not await is_super_admin(user, session):
            raise HTTPException(403, "无权转赠此卡")
    if card.status != "issued":
        raise HTTPException(400, f"状态 {card.status} 不可转赠")
    to_user = await session.get(User, to_user_id)
    if not to_user:
        raise HTTPException(404, "目标用户不存在")
    if to_user_id == card.holder_user_id:
        raise HTTPException(400, "不可转给自己")
    # H15：拒绝重复发起——已有 pending 转赠在途时不可再发
    existing = (
        await session.execute(
            select(CardTransfer).where(
                CardTransfer.card_id == card_id,
                CardTransfer.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, "此卡已有待确认的转赠（pending）")
    from_uid = card.holder_user_id
    # 不转 holder；等接收人 accept 后才转
    transfer = CardTransfer(
        card_id=card_id, from_user_id=from_uid, to_user_id=to_user_id,
        status="pending",
    )
    session.add(transfer)
    await session.commit()
    await session.refresh(transfer)
    return {
        "success": True, "transfer_id": transfer.id,
        "card_id": card_id, "from": from_uid, "to": to_user_id,
        "status": "pending",
        "hint": "接收人需在 7 天内调用 /transfer-card/{id}/accept 确认",
    }


@router.post("/transfer-card/{transfer_id}/accept")
async def accept_transfer(
    transfer_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """H15：接收人确认转赠 → holder 转移 + CardTransfer.status=accepted。"""
    from ...models import CardTransfer

    transfer = await session.get(CardTransfer, transfer_id)
    if not transfer:
        raise HTTPException(404, "转赠记录不存在")
    if transfer.status != "pending":
        raise HTTPException(400, f"转赠状态 {transfer.status} 不可确认")
    if transfer.to_user_id != user.id:
        raise HTTPException(403, "仅接收人可确认此转赠")
    card = await session.get(AssetCard, transfer.card_id)
    if not card:
        raise HTTPException(404, "卡券不存在")
    if card.status != "issued":
        raise HTTPException(400, f"卡券状态 {card.status} 已变化，转赠不可继续")
    # 行锁串行化并发确认（PG: FOR UPDATE；SQLite 静默降级）
    locked_card = (
        await session.execute(
            select(AssetCard).where(AssetCard.id == card.id).with_for_update()
        )
    ).scalar_one_or_none()
    if locked_card and locked_card.holder_user_id != transfer.from_user_id:
        # 转赠发起后原持卡人又被变更（如另一笔转赠已 accept），中止本次
        raise HTTPException(400, "卡券持有人已变化，转赠失效")
    # 转持有
    card.holder_user_id = transfer.to_user_id
    transfer.status = "accepted"
    await session.commit()
    return {
        "success": True, "transfer_id": transfer_id,
        "card_id": transfer.card_id, "status": "accepted",
    }


@router.post("/transfer-card/{transfer_id}/reject")
async def reject_transfer(
    transfer_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """H15：接收人拒绝转赠 → CardTransfer.status=rejected（holder 不变）。"""
    from ...models import CardTransfer

    transfer = await session.get(CardTransfer, transfer_id)
    if not transfer:
        raise HTTPException(404, "转赠记录不存在")
    if transfer.status != "pending":
        raise HTTPException(400, f"转赠状态 {transfer.status} 不可拒绝")
    if transfer.to_user_id != user.id:
        raise HTTPException(403, "仅接收人可拒绝此转赠")
    transfer.status = "rejected"
    await session.commit()
    return {"success": True, "transfer_id": transfer_id, "status": "rejected"}


@router.get("")
async def list_redemptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    card_id: int = Query(None),
    redeemer_id: int = Query(None),
    session: AsyncSession = Depends(get_session),
    _=Depends(get_current_user),
):
    # LOW：补过滤参数（原无过滤，只能拉全量）
    stmt = select(AssetRedemption)
    if card_id:
        stmt = stmt.where(AssetRedemption.card_id == card_id)
    if redeemer_id:
        stmt = stmt.where(AssetRedemption.redeemer_id == redeemer_id)
    stmt = stmt.order_by(AssetRedemption.id.desc())
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
