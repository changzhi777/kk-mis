"""复式记账测试（Voucher + JournalEntry + 过账 + 试算/资产负债表）。

覆盖 2026-07-15 标准复式改造：
- 借贷平衡创建 / 不平拒绝
- 过账更新余额
- 试算平衡（Σ借=Σ贷）
- 资产负债表扩展等式（assets + expense = liabilities + equity + revenue）
"""


def _ledger_ids(client, h):
    """取标准科目 id（库存现金 asset + 实收资本 equity + 管理费用 expense）。"""
    items = client.get("/admin/api/v1/finance/accounts", headers=h).json()["items"]
    by_name = {a["name"]: a["id"] for a in items}
    return by_name["库存现金"], by_name["实收资本"], by_name["管理费用"]


def test_create_voucher_balanced(client, auth_header):
    """借贷平衡的凭证创建成功（status=draft）。"""
    h = auth_header
    cash, eq, _ = _ledger_ids(client, h)
    r = client.post(
        "/admin/api/v1/finance/vouchers",
        headers=h,
        json={
            "voucher_date": "2026-07-15T10:00:00",
            "summary": "股东注资",
            "entries": [
                {"account_id": cash, "debit": 50000, "credit": 0},
                {"account_id": eq, "debit": 0, "credit": 50000},
            ],
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["debit_total"] == 50000.0
    assert d["credit_total"] == 50000.0
    assert d["status"] == "draft"


def test_create_voucher_unbalanced_rejected(client, auth_header):
    """借贷不平 → 400。"""
    h = auth_header
    cash, eq, _ = _ledger_ids(client, h)
    r = client.post(
        "/admin/api/v1/finance/vouchers",
        headers=h,
        json={
            "voucher_date": "2026-07-15T10:00:00",
            "summary": "不平测试",
            "entries": [
                {"account_id": cash, "debit": 100, "credit": 0},
                {"account_id": eq, "debit": 0, "credit": 200},
            ],
        },
    )
    assert r.status_code == 400
    assert "不平" in r.json()["detail"]


def test_post_voucher_balance_and_trial(client, auth_header):
    """过账后试算平衡表 Σ借=Σ贷。"""
    h = auth_header
    cash, eq, _ = _ledger_ids(client, h)
    v = client.post(
        "/admin/api/v1/finance/vouchers",
        headers=h,
        json={
            "voucher_date": "2026-07-15T10:00:00",
            "summary": "注资过账",
            "entries": [
                {"account_id": cash, "debit": 30000, "credit": 0},
                {"account_id": eq, "debit": 0, "credit": 30000},
            ],
        },
    ).json()
    r = client.post(f"/admin/api/v1/finance/vouchers/{v['id']}/post", headers=h)
    assert r.status_code == 200
    tb = client.get("/admin/api/v1/finance/reports/trial-balance", headers=h).json()
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


def test_balance_sheet_extended_equation(client, auth_header):
    """资产负债表扩展等式恒成立：assets + expense = liabilities + equity + revenue。"""
    h = auth_header
    cash, eq, expense = _ledger_ids(client, h)
    # 借费用 1000 + 贷现金 1000（一笔支出）
    v = client.post(
        "/admin/api/v1/finance/vouchers",
        headers=h,
        json={
            "voucher_date": "2026-07-15T10:00:00",
            "summary": "办公支出",
            "entries": [
                {"account_id": expense, "debit": 1000, "credit": 0},
                {"account_id": cash, "debit": 0, "credit": 1000},
            ],
        },
    ).json()
    client.post(f"/admin/api/v1/finance/vouchers/{v['id']}/post", headers=h)
    bs = client.get("/admin/api/v1/finance/reports/balance-sheet", headers=h).json()
    assert bs["balanced"] is True
    # 扩展等式
    left = bs["assets"] + bs["expenses"]
    right = bs["liabilities"] + bs["equity"] + bs.get("revenue", 0)
    assert abs(left - right) < 0.01


def test_double_post_rejected(client, auth_header):
    """已过账凭证重复过账 → 400。"""
    h = auth_header
    cash, eq, _ = _ledger_ids(client, h)
    v = client.post(
        "/admin/api/v1/finance/vouchers",
        headers=h,
        json={
            "voucher_date": "2026-07-15T10:00:00",
            "summary": "重复过账测试",
            "entries": [
                {"account_id": cash, "debit": 500, "credit": 0},
                {"account_id": eq, "debit": 0, "credit": 500},
            ],
        },
    ).json()
    client.post(f"/admin/api/v1/finance/vouchers/{v['id']}/post", headers=h)
    r2 = client.post(f"/admin/api/v1/finance/vouchers/{v['id']}/post", headers=h)
    assert r2.status_code == 400
    assert "已过账" in r2.json()["detail"]
