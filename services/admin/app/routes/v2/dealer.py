"""V2.0 经销商申请路由（M1.2 骨架）

经销商生命周期入口：提交申请 → 超管审批 → 开通。
详见 .zcf/plan/current/v2-app-redesign.md
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user, require_permission
from decimal import Decimal

from ...models import (
    Agent,
    User,
    V2DealerApplication,
    V2DealerBalance,
    V2DealerContract,
    V2DealerQualification,
)
from ...schemas.v2.dealer import (
    V2DealerApplicationCreate,
    V2DealerApplicationOut,
    V2DealerApplicationReject,
    V2DealerContractCreate,
    V2DealerContractOut,
    V2DealerQualificationCreate,
    V2DealerQualificationOut,
    V2DealerQualificationVerify,
)
from ...utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2/dealer", tags=["v2-dealer"])


@router.post("/application", response_model=V2DealerApplicationOut)
async def create_application(
    req: V2DealerApplicationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """提交经销商申请（任意登录用户）。

    申请轻量（省份 + 渠道备注）；主体资质在开通后于后台分步补充核验。
    防重复：同一 user 已有 pending/approved 申请则拒（409）。
    """
    existing = (
        await session.execute(
            select(V2DealerApplication).where(
                V2DealerApplication.user_id == user.id,
                V2DealerApplication.status.in_(("pending", "approved")),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "已存在待审/已通过的申请")
    app = V2DealerApplication(
        user_id=user.id,
        province_code=req.province_code,
        channel_note=req.channel_note,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return app


@router.get("/application", response_model=list[V2DealerApplicationOut])
async def list_applications(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """经销商申请列表（超管/运营；超管直通）。"""
    rows = (
        await session.execute(
            select(V2DealerApplication).order_by(V2DealerApplication.id.desc())
        )
    ).scalars().all()
    return rows


@router.post("/application/{app_id}/approve", response_model=V2DealerApplicationOut)
async def approve_application(
    app_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """审批通过经销商申请（超管）。

    TODO M1.3：approve 后自动建 Agent（region_code=province_code）+ V2DealerBalance
    + 进入"补资质/签合同"状态。M1.2 骨架仅改申请状态。
    """
    app = await session.get(V2DealerApplication, app_id)
    if not app:
        raise HTTPException(404, "申请不存在")
    if app.status != "pending":
        raise HTTPException(409, f"申请状态 {app.status}，不可审批")
    app.status = "approved"
    app.approved_by = user.id
    app.approved_at = utcnow()
    # M1.3：approve 后自动建经销商身份（Agent，region_code 锁省归属）+ 预付余额账户。
    # Agent.commission_rate 占位 0（V2.0 改返点，不用 commission）；promo_code 留空，
    # M2 推广码生成（referral_code 复用 mis-system）。
    agent = Agent(
        user_id=app.user_id,
        region_code=app.province_code,
        commission_rate=Decimal("0"),
        status=True,
    )
    session.add(agent)
    await session.flush()  # 拿 agent.id
    session.add(V2DealerBalance(agent_id=agent.id))
    await session.commit()
    await session.refresh(app)
    return app


@router.post("/application/{app_id}/reject", response_model=V2DealerApplicationOut)
async def reject_application(
    app_id: int,
    req: V2DealerApplicationReject,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """驳回经销商申请（超管）。"""
    app = await session.get(V2DealerApplication, app_id)
    if not app:
        raise HTTPException(404, "申请不存在")
    if app.status != "pending":
        raise HTTPException(409, f"申请状态 {app.status}，不可驳回")
    app.status = "rejected"
    app.approved_by = user.id
    app.approved_at = utcnow()
    app.reject_reason = req.reason
    await session.commit()
    await session.refresh(app)
    return app


# ===== 经销商合同（M1.4）=====
@router.post("/contract", response_model=V2DealerContractOut)
async def create_contract(
    req: V2DealerContractCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """签经销商合同（超管）。

    建合同记录（service_fee_mode/rate/rebate_tiers 占位，具体值待合同阶段定），
    status=active，signed_at=now。
    TODO M1.5：资质录入（营业执照/法人）+ 平台核验，挂合同签订流。
    """
    contract = V2DealerContract(
        agent_id=req.agent_id,
        start_date=req.start_date,
        end_date=req.end_date,
        service_fee_mode=req.service_fee_mode,
        service_fee_rate=req.service_fee_rate,
        rebate_tiers=req.rebate_tiers,
        status="active",
        signed_at=utcnow(),
    )
    session.add(contract)
    await session.commit()
    await session.refresh(contract)
    return contract


@router.get("/contract", response_model=list[V2DealerContractOut])
async def list_contracts(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """合同列表（超管）。"""
    rows = (
        await session.execute(
            select(V2DealerContract).order_by(V2DealerContract.id.desc())
        )
    ).scalars().all()
    return rows


# ===== 经销商主体资质（M1.5 续）=====
@router.post("/qualification", response_model=V2DealerQualificationOut)
async def submit_qualification(
    req: V2DealerQualificationCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """经销商提交/补充主体资质（当前登录经销商自己提交）。

    一个 agent 一条资质（业务语义）：
    - 无记录 → 新建 pending；
    - 有记录且未核验通过 → merge 非空字段更新（支持分步补营业执照/法人/信用代码）；
    - 已 verified → 409（变更需联系平台）。
    """
    agent = (
        await session.execute(select(Agent).where(Agent.user_id == user.id))
    ).scalars().first()
    if not agent:
        raise HTTPException(403, "尚未开通经销商身份，无法提交资质")

    existing = (
        await session.execute(
            select(V2DealerQualification).where(
                V2DealerQualification.agent_id == agent.id
            )
        )
    ).scalars().first()
    if existing:
        if existing.status == "verified":
            raise HTTPException(409, "已有核验通过的资质，如需变更请联系平台")
        existing.company_name = req.company_name
        if req.legal_person is not None:
            existing.legal_person = req.legal_person
        if req.business_license_no is not None:
            existing.business_license_no = req.business_license_no
        if req.business_license_url is not None:
            existing.business_license_url = req.business_license_url
        existing.status = "pending"  # 重新提交重置核验
        existing.reject_reason = None
        await session.commit()
        await session.refresh(existing)
        return existing

    qual = V2DealerQualification(
        agent_id=agent.id,
        company_name=req.company_name,
        legal_person=req.legal_person,
        business_license_no=req.business_license_no,
        business_license_url=req.business_license_url,
    )
    session.add(qual)
    await session.commit()
    await session.refresh(qual)
    return qual


@router.get("/qualification", response_model=list[V2DealerQualificationOut])
async def list_qualifications(
    agent_id: Optional[int] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """资质列表（超管；可按 agent_id / status 过滤）。"""
    stmt = select(V2DealerQualification).order_by(V2DealerQualification.id.desc())
    if agent_id is not None:
        stmt = stmt.where(V2DealerQualification.agent_id == agent_id)
    if status is not None:
        stmt = stmt.where(V2DealerQualification.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return rows


@router.post(
    "/qualification/{qual_id}/verify", response_model=V2DealerQualificationOut
)
async def verify_qualification(
    qual_id: int,
    req: V2DealerQualificationVerify,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(require_permission("v2:dealer:manage")),
):
    """平台核验经销商资质（超管；通过/驳回合一）。

    - action=verify → status=verified + verified_by/at；
    - action=reject → status=rejected + reject_reason（必填）。
    仅 pending/rejected 可核验（verified 不重复核验）。
    """
    qual = await session.get(V2DealerQualification, qual_id)
    if not qual:
        raise HTTPException(404, "资质记录不存在")
    if qual.status == "verified":
        raise HTTPException(409, "资质已核验通过，不可重复核验")
    if req.action == "reject" and not req.reason:
        raise HTTPException(422, "驳回需提供原因")

    if req.action == "verify":
        qual.status = "verified"
        qual.reject_reason = None
    else:
        qual.status = "rejected"
        qual.reject_reason = req.reason
    qual.verified_by = user.id
    qual.verified_at = utcnow()
    await session.commit()
    await session.refresh(qual)
    return qual
