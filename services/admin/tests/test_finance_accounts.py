"""finance accounts 路由测试 — 账户 CRUD + 删除保护。

复用 conftest 的 session 级 `client` + `auth_header` fixture（与 test_finance.py 同风格）。
"""

from __future__ import annotations


def _create_account(client, headers, *, name: str, type_: str = "cash", balance: float = 0):
    r = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": name, "type": type_, "balance": balance, "sort": 0, "status": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _list_ids(client, headers):
    items = client.get("/admin/api/v1/finance/accounts", headers=headers).json()["items"]
    return {a["id"] for a in items}


def test_account_crud_create_list_update_delete(client, auth_header):
    """完整 CRUD：create → list 含新账户 → update 部分字段 → delete → list 不再含。"""
    h = auth_header

    # ── create ─────────────────────────────────────────────
    acc = _create_account(client, h, name="CRUD测试账户", type_="bank", balance=1234.56)
    aid = acc["id"]
    assert acc["name"] == "CRUD测试账户"
    assert acc["type"] == "bank"
    assert float(acc["balance"]) == 1234.56

    # ── list（至少含新建）──────────────────────────────────
    assert aid in _list_ids(client, h)

    # ── update（部分字段：name + sort；balance 不在 AccountUpdate 故不变）──
    r = client.put(
        f"/admin/api/v1/finance/accounts/{aid}",
        json={"name": "CRUD测试账户-改名", "sort": 9},
        headers=h,
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["name"] == "CRUD测试账户-改名"
    assert updated["sort"] == 9
    # balance 未被重置（AccountUpdate 不含 balance 字段，exclude_unset 跳过）
    assert float(updated["balance"]) == 1234.56

    # ── delete ─────────────────────────────────────────────
    r = client.delete(f"/admin/api/v1/finance/accounts/{aid}", headers=h)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # ── 再 list 确认已删 ───────────────────────────────────
    assert aid not in _list_ids(client, h)


def test_update_nonexistent_account_returns_404(client, auth_header):
    """PUT 不存在的 aid → 404。"""
    r = client.put(
        "/admin/api/v1/finance/accounts/999999",
        json={"name": "不存在"},
        headers=auth_header,
    )
    assert r.status_code == 404


def test_delete_account_with_transactions_rejected(client, auth_header):
    """账户存在流水时不可删（路由层 400 防数据孤儿）。"""
    h = auth_header
    acc = _create_account(client, h, name="有流水不可删账户", type_="cash")
    cat = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "配套科目-删账测试", "type": "income"},
        headers=h,
    ).json()

    tx = client.post(
        "/admin/api/v1/finance/transactions",
        json={
            "account_id": acc["id"],
            "category_id": cat["id"],
            "type": "income",
            "amount": 50,
            "transaction_date": "2026-07-12",
        },
        headers=h,
    )
    assert tx.status_code == 200

    r = client.delete(f"/admin/api/v1/finance/accounts/{acc['id']}", headers=h)
    assert r.status_code == 400
    assert "流水" in r.json()["detail"]

    # 账户仍应存在（未被误删）
    assert acc["id"] in _list_ids(client, h)
