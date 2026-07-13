"""防伪核销 mock 接口（决策 #3 重构 2026-07-13）

Phase 1：本地根据 unique_code 存在与否返回 verified（mock 上链验证）
Phase 2：替换为 Hyperledger Fabric chaincode verifyCard 调用
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...models import AssetCard

router = APIRouter(prefix="/api/v1/asset/cards/verify", tags=["asset-verify"])


@router.get("/{unique_code}")
async def verify_card(
    unique_code: str,
    session: AsyncSession = Depends(get_session),
):
    """防伪核销：返回真伪 + 来源（Phase 1 mock，Phase 2 接 Fabric）"""
    if not unique_code or len(unique_code) != 64:
        raise HTTPException(400, "unique_code 必须是 64 位 hex 字符串")

    card = (
        await session.execute(
            select(AssetCard).where(AssetCard.unique_code == unique_code)
        )
    ).scalar_one_or_none()
    if card is None:
        return {
            "unique_code": unique_code,
            "verified": False,
            "reason": "unique_code 不存在或已被撤销",
        }

    # Phase 1 mock：存在即 verified
    # Phase 2：调 Fabric chaincode.verifyCard(unique_code) 对账
    return {
        "unique_code": unique_code,
        "verified": True,
        "card_no_prefix": card.card_no[:4] + "****" + card.card_no[-4:],  # 隐藏中间
        "batch_id": card.batch_id,
        "type_id": card.type_id,
        "status": card.status,
        "blockchain_tx_hash": card.blockchain_tx_hash,
        "last_verified_at": card.last_verified_at.isoformat() if card.last_verified_at else None,
    }