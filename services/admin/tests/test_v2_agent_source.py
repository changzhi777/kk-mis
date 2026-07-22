"""1user→1agent 加固测试（Agent.source）：user 同时有 V1 区域代理 + V2 经销商 agent，
V2 端点必须取 V2 agent（source=v2），不能取错 V1 导致资金/激活错位。"""
import asyncio
import uuid

from sqlalchemy import select

from app import db
from app.models import Agent


def _register(client, username):
    pwd = "test1234"
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": username, "password": pwd, "name": username},
    )
    assert r.status_code == 200, r.text
    token = r.json().get("access_token") or client.post(
        "/admin/api/v1/auth/login",
        json={"username": username, "password": pwd},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _open_dealer(client, admin_h, dealer_h):
    app = client.post(
        "/admin/api/v2/dealer/application",
        json={"province_code": "GD"},
        headers=dealer_h,
    ).json()
    client.post(f"/admin/api/v2/dealer/application/{app['id']}/approve", headers=admin_h)


async def _insert_v1_agent(user_id: int) -> int:
    """给 user 插入一个 V1 区域代理 agent（模拟历史数据），返回其 id。"""
    async with db.SessionLocal() as s:
        a = Agent(
            user_id=user_id,
            name="V1历史代理",
            region_code="V1OLD",
            commission_rate=0,
            status=True,
            source="v1",
        )
        s.add(a)
        await s.commit()
        await s.refresh(a)
        return a.id


def test_v2_endpoints_use_v2_agent_not_v1(client, auth_header):
    """user 有 V1+V2 agent，V2 端点（balance/promo）取 V2 agent，不受 V1 干扰。"""
    admin = auth_header
    sfx = uuid.uuid4().hex[:6]
    dealer = _register(client, f"vs_{sfx}")
    _open_dealer(client, admin, dealer)
    me = client.get("/admin/api/v1/auth/me", headers=dealer).json()
    user_id = me["id"]

    # 插入 V1 agent（历史区域代理，无 V2DealerBalance）
    v1_id = asyncio.run(_insert_v1_agent(user_id))

    # V2 balance 端点必须 200（取 V2 agent + 其 balance），加固前会因取 V1 agent
    # （无 V2DealerBalance）而 500
    r = client.get("/admin/api/v2/dealer/balance", headers=dealer)
    assert r.status_code == 200, r.text
    assert float(r.json()["balance"]) == 0.0  # V2 agent 未充值

    # 推广码：V2 agent 懒生成 promo_code，V1 agent 不受影响
    promo = client.get("/admin/api/v2/dealer/promo-code", headers=dealer).json()
    assert "promo_code" in promo
    assert len(promo["promo_code"]) == 8

    # 确认 V1 agent 仍存在（未误删）
    async def _check_v1():
        async with db.SessionLocal() as s:
            return (
                await s.execute(select(Agent).where(Agent.id == v1_id))
            ).scalar_one_or_none()

    v1 = asyncio.run(_check_v1())
    assert v1 is not None
    assert v1.source == "v1"
