"""V2.0 实名认证测试（M2.6：三要素，注册即实名，id_card 存 SHA256 hash）"""
import asyncio
import hashlib
import uuid

from sqlalchemy import select

from app import db
from app.models import User


def _register(client, username: str) -> dict:
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


def test_realname_verify_and_me(client, auth_header):
    """提交实名 → verified + 脱敏展示；GET me 一致。"""
    h = _register(client, f"rn_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/realname/verify",
        json={"real_name": "张三", "id_card_no": "110101199001011234"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["realname_status"] == "verified"
    assert data["real_name"] == "张三"
    assert "*" in data["id_card_masked"]

    me = client.get("/admin/api/v2/realname/me", headers=h).json()
    assert me["realname_status"] == "verified"
    assert me["real_name"] == "张三"


def test_realname_duplicate_rejected(client, auth_header):
    """已 verified 再提交 → 409（防覆盖）。"""
    h = _register(client, f"rd_{uuid.uuid4().hex[:6]}")
    client.post(
        "/admin/api/v2/realname/verify",
        json={"real_name": "李四", "id_card_no": "110101199002022345"},
        headers=h,
    )
    r = client.post(
        "/admin/api/v2/realname/verify",
        json={"real_name": "李四2", "id_card_no": "110101199002022345"},
        headers=h,
    )
    assert r.status_code == 409


def test_realname_id_card_hashed_not_plaintext(client, auth_header):
    """身份证号存 SHA256 hash，DB 无明文 id_card 列。"""
    id_card = "110101199003033456"
    h = _register(client, f"rh_{uuid.uuid4().hex[:6]}")
    client.post(
        "/admin/api/v2/realname/verify",
        json={"real_name": "王五", "id_card_no": id_card},
        headers=h,
    )

    expected_hash = hashlib.sha256(id_card.encode()).hexdigest()

    async def _q():
        async with db.SessionLocal() as s:
            return (
                await s.execute(select(User).where(User.id_card_hash == expected_hash))
            ).scalar_one_or_none()

    user = asyncio.run(_q())
    assert user is not None
    assert user.real_name == "王五"
    assert user.realname_status == "verified"
    # User 模型无明文 id_card 列（仅 id_card_hash）
    assert getattr(user, "id_card_no", None) is None
