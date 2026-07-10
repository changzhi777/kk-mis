"""卡券批次路由 + 生成卡券（卡号16位 + 密码6位 bcrypt 哈希）"""
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import require_permission
from ...models import AssetCard, AssetCardBatch, AssetCardType
from ...schemas.asset import BatchCreate, BatchOut, GenerateCardsRequest, GeneratedCard
from ...security import hash_password

router = APIRouter(prefix="/api/v1/asset/batches", tags=["asset-batch"])


def _gen_no() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(16))


def _gen_pwd() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))


@router.get("")
async def list_batches(
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:batch:list")),
):
    items = (
        await session.execute(select(AssetCardBatch).order_by(AssetCardBatch.id.desc()))
    ).scalars().all()
    return {"items": [BatchOut.model_validate(b).model_dump() for b in items]}


@router.post("", response_model=BatchOut)
async def create_batch(
    req: BatchCreate,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:batch:save")),
):
    type_ = await session.get(AssetCardType, req.type_id)
    if not type_:
        raise HTTPException(400, "卡券类型不存在")
    b = AssetCardBatch(
        type_id=req.type_id, name=req.name, quantity=req.quantity,
        generated=0, status="draft", valid_until=req.valid_until,
    )
    session.add(b)
    await session.commit()
    await session.refresh(b)
    return BatchOut.model_validate(b)


@router.post("/{batch_id}/generate")
async def generate_cards(
    batch_id: int,
    req: GenerateCardsRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:batch:save")),
):
    """生成卡券：返回明文卡号+密码（一次性，用于导出/打印），DB 存哈希"""
    b = await session.get(AssetCardBatch, batch_id)
    if not b:
        raise HTTPException(404, "批次不存在")
    type_ = await session.get(AssetCardType, b.type_id)
    if not type_:
        raise HTTPException(400, "类型不存在")

    generated: list[GeneratedCard] = []
    for _ in range(req.quantity):
        card_no = _gen_no()
        # 唯一性校验（冲突重生成，最多重试 5 次）
        for _retry in range(5):
            exists = (
                await session.execute(select(AssetCard.id).where(AssetCard.card_no == card_no))
            ).first()
            if not exists:
                break
            card_no = _gen_no()
        pwd = _gen_pwd()
        card = AssetCard(
            batch_id=batch_id, type_id=b.type_id, card_no=card_no,
            password_hash=hash_password(pwd), face_value=type_.face_value,
            status="draft", valid_until=b.valid_until,
        )
        session.add(card)
        generated.append(GeneratedCard(card_no=card_no, password=pwd))
    b.generated = (b.generated or 0) + req.quantity
    if b.status == "draft":
        b.status = "active"
    await session.commit()
    return {
        "generated": len(generated),
        "batch_generated": b.generated,
        "cards": [g.model_dump() for g in generated],
    }


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:batch:save")),
):
    b = await session.get(AssetCardBatch, batch_id)
    if not b:
        raise HTTPException(404, "批次不存在")
    await session.delete(b)
    await session.commit()
    return {"success": True}
