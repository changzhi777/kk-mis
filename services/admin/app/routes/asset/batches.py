"""卡券批次路由 + 生成卡券（卡号16位 + 密码6位 bcrypt 哈希）

2026-07-13 性能优化：批量生成 + 信任零碰撞
- 内存 set 去重（避免同批次内重复）
- DB unique 索引兜底（防理论碰撞 + 跨请求）
- 一次 add_all + flush（避免 N 次 session.add + N^2 次 SELECT）
"""
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
from ...utils import utcnow

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


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(
    batch_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(require_permission("asset:batch:list")),
):
    """查单个批次详情。"""
    b = await session.get(AssetCardBatch, batch_id)
    if not b:
        raise HTTPException(404, "批次不存在")
    return BatchOut.model_validate(b)


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
    """生成卡券：返回明文卡号+密码（一次性，用于导出/打印），DB 存哈希

    决策 #3 重构（2026-07-13）：
    - 生成 64 位 unique_code（防伪，Phase 2 接入 Hyperledger Fabric）
    - 生成 mock blockchain_tx_hash（uuid）
    - 生成 QR URL（防伪核销页）
    """
    import os
    import uuid

    b = await session.get(AssetCardBatch, batch_id)
    if not b:
        raise HTTPException(404, "批次不存在")
    type_ = await session.get(AssetCardType, b.type_id)
    if not type_:
        raise HTTPException(400, "类型不存在")

    base_url = os.getenv("ANTICOUNTERFEIT_BASE_URL", "https://aisport.tech/oa/verify")
    unit_price = b.unit_price or type_.unit_price

    # 2026-07-13 性能优化：批量生成 + 信任零碰撞
    # - card_no: 16 位数字空间 10^16，N=1000 张碰撞概率 ~10^-11（数学上不可能）
    # - unique_code: 256 bit 熵，N=10^9 张碰撞概率 ~10^-49（实际不可能）
    # 因此：直接生成不查 DB（trust zero collision），最后用一次 unique 索引验重
    # N 张 1 次 commit（不用 N 次 session.add + 10000 次 SELECT）
    now = utcnow()
    cards: list[AssetCard] = []
    generated: list[GeneratedCard] = []
    seen_card_nos: set[str] = set()  # 内存去重（本批次内）
    for _ in range(req.quantity):
        card_no = _gen_no()
        while card_no in seen_card_nos:
            card_no = _gen_no()
        seen_card_nos.add(card_no)

        unique_code = secrets.token_hex(32)  # 64 hex chars
        pwd = _gen_pwd()
        mock_tx_hash = uuid.uuid4().hex
        qr_url = f"{base_url}/{unique_code}"

        cards.append(
            AssetCard(
                batch_id=batch_id,
                type_id=b.type_id,
                card_no=card_no,
                unique_code=unique_code,
                blockchain_tx_hash=mock_tx_hash,
                qr_url=qr_url,
                password_hash=hash_password(pwd),
                face_value=type_.face_value,
                unit_price=unit_price,
                status="draft",
                valid_until=b.valid_until,
                created_at=now,
            )
        )
        generated.append(GeneratedCard(card_no=card_no, password=pwd))

    # 一次性 bulk save（SQLAlchemy 2.0 用 add_all + flush 一次 INSERT 多行）
    session.add_all(cards)
    await session.flush()  # 触发 INSERT + unique 索引验重（DB 兜底）

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
