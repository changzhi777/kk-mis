"""V2.0 经销商域端到端测试（M1.7）

覆盖经销商生命周期：申请 → 超管审批（开通 Agent+Balance）→ 签合同 → 补资质（分步 merge）→
平台核验 → 看套餐目录；含权限隔离（staff 无 v2:dealer:manage → 403）+ 边界
（申请防重复 / 非 dealer 提交资质 403 / verified 重提 409 / 驳回无 reason 422）。

详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
"""
import asyncio
import uuid

from sqlalchemy import select

from app import db
from app.models import Agent


def _register_dealer(client, username: str) -> dict:
    """注册经销商测试用户（绑 staff 角色），返回 auth_header。"""
    pwd = "dealer123"
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": username, "password": pwd, "name": username},
    )
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    if not token:  # register 未直返 token → 单独 login
        token = client.post(
            "/admin/api/v1/auth/login",
            json={"username": username, "password": pwd},
        ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _get_agent_id(user_id: int) -> int | None:
    """跨 event loop 查 dealer user 的 agent_id（复用 test_payment_route_notify 验证过的模式）。"""
    async def _q():
        async with db.SessionLocal() as s:
            agent = (
                await s.execute(select(Agent).where(Agent.user_id == user_id))
            ).scalars().first()
            return agent.id if agent else None

    return asyncio.run(_q())


def _open_dealer(client, admin_header, dealer_header, province="GD") -> int:
    """跑通 申请→审批→开通，返回 agent_id。"""
    app = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": province},
        headers=dealer_header,
    ).json()
    client.post(
        f"/admin/api/v2/dealer/application/{app['id']}/approve", headers=admin_header
    )
    me = client.get("/admin/api/v1/auth/me", headers=dealer_header).json()
    return _get_agent_id(me["id"])


# ── 核心 E2E：经销商生命周期 ──────────────────────────────────────


def test_dealer_full_lifecycle(client, auth_header):
    """申请 → 审批开通 → 签合同 → 补资质(分步 merge) → 核验 → 看套餐。"""
    admin = auth_header
    suffix = uuid.uuid4().hex[:6]
    dealer = _register_dealer(client, f"dealer_{suffix}")

    # 1. 提交申请
    app = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": "GD", "channel_note": "测试渠道"},
        headers=dealer,
    ).json()
    assert app["status"] == "pending"
    assert app["province_code"] == "GD"

    # 2. 超管看申请列表（含该申请）
    listing = client.get("/admin/api/v2/dealer/application", headers=admin).json()
    assert any(a["id"] == app["id"] for a in listing)

    # 3. 超管审批通过 → 开通（建 Agent + Balance）
    approved = client.post(
        f"/admin/api/v2/dealer/application/{app['id']}/approve", headers=admin
    ).json()
    assert approved["status"] == "approved"

    # 4. 超管签合同（agent_id 查 DB 拿）
    agent_id = _get_agent_id(
        client.get("/admin/api/v1/auth/me", headers=dealer).json()["id"]
    )
    assert agent_id is not None  # 审批后必建 Agent
    contract = client.post(
        "/admin/api/v2/dealer/contract",
        json={
            "agent_id": agent_id,
            "start_date": "2026-07-22T00:00:00",
            "end_date": "2027-07-22T00:00:00",
            "service_fee_mode": "per_unit",
        },
        headers=admin,
    ).json()
    assert contract["status"] == "active"
    # 4b. 合同列表含刚建的
    contracts = client.get("/admin/api/v2/dealer/contract", headers=admin).json()
    assert any(c["agent_id"] == agent_id for c in contracts)

    # 5. 经销商补资质（首次，仅 company_name）
    qual = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": f"测试经销商_{suffix}"},
        headers=dealer,
    ).json()
    assert qual["status"] == "pending"
    assert qual["legal_person"] is None
    qual_id = qual["id"]

    # 6. 分步补资质（merge legal_person + license_no，同一条记录）
    merged = client.post(
        "/admin/api/v2/dealer/qualification",
        json={
            "company_name": f"测试经销商_{suffix}",
            "legal_person": "张三",
            "business_license_no": "91TEST001",
        },
        headers=dealer,
    ).json()
    assert merged["id"] == qual_id  # upsert 同一条
    assert merged["legal_person"] == "张三"
    assert merged["business_license_no"] == "91TEST001"

    # 7. 超管核验通过
    verified = client.post(
        f"/admin/api/v2/dealer/qualification/{qual_id}/verify",
        json={"action": "verify"},
        headers=admin,
    ).json()
    assert verified["status"] == "verified"
    assert verified["verified_by"] is not None

    # 8. 经销商看套餐目录（published only；可为空 list）
    products = client.get("/admin/api/v2/products", headers=dealer)
    assert products.status_code == 200
    assert isinstance(products.json(), list)


# ── 边界 + 权限隔离 ──────────────────────────────────────────────


def test_application_duplicate_rejected(client, auth_header):
    """同一 user 已有 pending 申请 → 再申请 409。"""
    dealer = _register_dealer(client, f"dup_{uuid.uuid4().hex[:6]}")
    r1 = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": "GD"},
        headers=dealer,
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": "BJ"},
        headers=dealer,
    )
    assert r2.status_code == 409


def test_qualification_requires_agent(client, auth_header):
    """非经销商（未开通，无 agent）提交资质 → 403。"""
    plain = _register_dealer(client, f"plain_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "无身份公司"},
        headers=plain,
    )
    assert r.status_code == 403


def test_qualification_verified_no_resubmit(client, auth_header):
    """已 verified 资质再提交 → 409。"""
    admin = auth_header
    dealer = _register_dealer(client, f"ver_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, admin, dealer)
    qual = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "公司A"},
        headers=dealer,
    ).json()
    client.post(
        f"/admin/api/v2/dealer/qualification/{qual['id']}/verify",
        json={"action": "verify"},
        headers=admin,
    )
    r = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "新公司"},
        headers=dealer,
    )
    assert r.status_code == 409


def test_qualification_reject_requires_reason(client, auth_header):
    """驳回资质但无 reason → 422；带 reason → 200 rejected。"""
    admin = auth_header
    dealer = _register_dealer(client, f"rej_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, admin, dealer)
    qual = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "公司B"},
        headers=dealer,
    ).json()
    # 无 reason → 422
    r = client.post(
        f"/admin/api/v2/dealer/qualification/{qual['id']}/verify",
        json={"action": "reject"},
        headers=admin,
    )
    assert r.status_code == 422
    # 带 reason → 200
    r2 = client.post(
        f"/admin/api/v2/dealer/qualification/{qual['id']}/verify",
        json={"action": "reject", "reason": "执照不清"},
        headers=admin,
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"
    assert r2.json()["reject_reason"] == "执照不清"


def test_qualification_reverify_after_resubmit(client, auth_header):
    """rejected 资质重新提交(reset pending)后可再次核验通过。"""
    admin = auth_header
    dealer = _register_dealer(client, f"rev_{uuid.uuid4().hex[:6]}")
    _open_dealer(client, admin, dealer)
    qual = client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "公司C"},
        headers=dealer,
    ).json()
    client.post(
        f"/admin/api/v2/dealer/qualification/{qual['id']}/verify",
        json={"action": "reject", "reason": "材料不全"},
        headers=admin,
    )
    # 重新提交（reset pending + 补法人）
    client.post(
        "/admin/api/v2/dealer/qualification",
        json={"company_name": "公司C", "legal_person": "李四"},
        headers=dealer,
    )
    r = client.post(
        f"/admin/api/v2/dealer/qualification/{qual['id']}/verify",
        json={"action": "verify"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "verified"


def test_permission_isolation_staff_cannot_manage(client, auth_header):
    """经销商(staff)无 v2:dealer:manage → 审批/核验/合同 403。"""
    dealer = _register_dealer(client, f"iso_{uuid.uuid4().hex[:6]}")
    # 审批 → 403
    assert client.post(
        "/admin/api/v2/dealer/application/1/approve", headers=dealer
    ).status_code == 403
    # 核验 → 403
    assert client.post(
        "/admin/api/v2/dealer/qualification/1/verify",
        json={"action": "verify"},
        headers=dealer,
    ).status_code == 403
    # 签合同 → 403
    assert client.post(
        "/admin/api/v2/dealer/contract",
        json={
            "agent_id": 1,
            "start_date": "2026-07-22T00:00:00",
            "end_date": "2027-07-22T00:00:00",
        },
        headers=dealer,
    ).status_code == 403
    # 看申请列表（管理端）→ 403
    assert client.get(
        "/admin/api/v2/dealer/application", headers=dealer
    ).status_code == 403
