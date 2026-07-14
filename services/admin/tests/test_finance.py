"""财务管理关键路径测试（账户→科目→流水→余额联动）

覆盖决策 #4（记账统计）+ 决策 #5（低并发，无 OLAP/缓存）：
- 流水创建触发账户余额联动（业务关键路径）
- 流水类型与科目类型必须匹配（防数据错误）
- 报表按 type 聚合（ECharts 报表数据源）
- CSV 导出（utils.to_csv 复用）
"""


def _list_account_by_id(client, headers, account_id):
    """accounts 没有 GET /{id}，只能从 list 里 find。"""
    items = client.get("/admin/api/v1/finance/accounts", headers=headers).json()["items"]
    for a in items:
        if a["id"] == account_id:
            return a
    return None


def test_account_balance_changes_on_transaction(client, auth_header):
    """创建收入流水 → 账户余额自动 +amount；支出 → -amount。"""
    h = auth_header
    # 建账户 + 2 个科目（一收一支）
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "现金", "type": "cash", "balance": 1000},
        headers=h,
    ).json()
    cat_in = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "销售收入", "type": "income"},
        headers=h,
    ).json()
    cat_out = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "办公费", "type": "expense"},
        headers=h,
    ).json()

    # 收入 500 → 余额 1500
    client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_in["id"],
              "type": "income", "amount": 500, "transaction_date": "2026-07-12"},
        headers=h,
    )
    acc_now = _list_account_by_id(client, h, acc["id"])
    assert acc_now is not None
    assert float(acc_now["balance"]) == 1500.0

    # 支出 200 → 余额 1300
    client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_out["id"],
              "type": "expense", "amount": 200, "transaction_date": "2026-07-12"},
        headers=h,
    )
    acc_now = _list_account_by_id(client, h, acc["id"])
    assert float(acc_now["balance"]) == 1300.0


def test_transaction_type_must_match_category_type(client, auth_header):
    """流水类型与科目类型不符 → 400（防数据错误）。"""
    h = auth_header
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "对公账户", "type": "bank", "balance": 0},
        headers=h,
    ).json()
    cat_expense = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "工资", "type": "expense"},
        headers=h,
    ).json()
    # 创建 income 流水但关联 expense 科目 → 应被拒
    r = client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_expense["id"],
              "type": "income", "amount": 100, "transaction_date": "2026-07-12"},
        headers=h,
    )
    assert r.status_code == 400
    assert "类型" in r.json()["detail"]


def test_report_summary_aggregates_income_expense(client, auth_header):
    """报表 summary 返回 income / expense / balance 聚合（决策 #4 记账数据源）。"""
    h = auth_header
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "汇总账户", "type": "bank", "balance": 0},
        headers=h,
    ).json()
    cat_in = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "营业收入", "type": "income"},
        headers=h,
    ).json()
    cat_out = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "水电费", "type": "expense"},
        headers=h,
    ).json()
    # 3 笔收入 + 2 笔支出
    for _ in range(3):
        client.post(
            "/admin/api/v1/finance/transactions",
            json={"account_id": acc["id"], "category_id": cat_in["id"],
                  "type": "income", "amount": 100, "transaction_date": "2026-07-12"},
            headers=h,
        )
    for _ in range(2):
        client.post(
            "/admin/api/v1/finance/transactions",
            json={"account_id": acc["id"], "category_id": cat_out["id"],
                  "type": "expense", "amount": 50, "transaction_date": "2026-07-12"},
            headers=h,
        )
    # summary 响应：{income, expense, balance, count}
    # 注意：DB 是 session 级共享，前面测试可能也建了 income/expense，所以用 >= 比较
    summary = client.get("/admin/api/v1/finance/reports/summary", headers=h).json()
    assert summary["income"] >= 300.0
    assert summary["expense"] >= 100.0
    assert summary["balance"] == summary["income"] - summary["expense"]  # 恒等式


def test_finance_export_csv(client, auth_header):
    """CSV 导出接口在 transactions 路径（utils.to_csv 复用，UTF-8 BOM Excel 双击不乱码）。"""
    h = auth_header
    # 建数据让 export 不空
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "导出账户", "type": "bank", "balance": 0},
        headers=h,
    ).json()
    cat = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "导出测试科目", "type": "income"},
        headers=h,
    ).json()
    client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat["id"],
              "type": "income", "amount": 999, "transaction_date": "2026-07-12"},
        headers=h,
    )
    r = client.get("/admin/api/v1/finance/transactions/export", headers=h)
    assert r.status_code == 200
    # BOM 头（Excel 双击不乱码）
    assert r.content[:3] == b"\xef\xbb\xbf"
    # 内容至少含表头
    body = r.content.decode("utf-8-sig")
    assert "amount" in body or "金额" in body  # 列名中英至少一种


def test_update_transaction_reverses_and_applies_balance(client, auth_header):
    """PUT 更新流水：反向旧余额 → 应用新余额（改金额/类型时余额正确联动）。"""
    h = auth_header
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "PUT测试账户", "type": "cash", "balance": 0},
        headers=h,
    ).json()
    cat_in = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "PUT收入", "type": "income"},
        headers=h,
    ).json()
    cat_out = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "PUT支出", "type": "expense"},
        headers=h,
    ).json()
    # 建收入 500 → 余额 500
    tx = client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_in["id"],
              "type": "income", "amount": 500, "transaction_date": "2026-07-12"},
        headers=h,
    ).json()
    assert float(_list_account_by_id(client, h, acc["id"])["balance"]) == 500.0

    # PUT 改成支出 200 → 反向旧(+500→0) + 应用新(-200) → 余额 -200
    r = client.put(
        f"/admin/api/v1/finance/transactions/{tx['id']}",
        json={"account_id": acc["id"], "category_id": cat_out["id"],
              "type": "expense", "amount": 200, "transaction_date": "2026-07-12"},
        headers=h,
    )
    assert r.status_code == 200
    assert float(_list_account_by_id(client, h, acc["id"])["balance"]) == -200.0


def test_report_by_account(client, auth_header):
    """by-account 按账户聚合收入/支出/结余。"""
    h = auth_header
    acc = client.post(
        "/admin/api/v1/finance/accounts",
        json={"name": "by-account测试", "type": "bank", "balance": 0},
        headers=h,
    ).json()
    cat_in = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "byAcc收入", "type": "income"},
        headers=h,
    ).json()
    cat_out = client.post(
        "/admin/api/v1/finance/categories",
        json={"name": "byAcc支出", "type": "expense"},
        headers=h,
    ).json()
    client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_in["id"],
              "type": "income", "amount": 800, "transaction_date": "2026-07-12"},
        headers=h,
    )
    client.post(
        "/admin/api/v1/finance/transactions",
        json={"account_id": acc["id"], "category_id": cat_out["id"],
              "type": "expense", "amount": 300, "transaction_date": "2026-07-12"},
        headers=h,
    )
    r = client.get("/admin/api/v1/finance/reports/by-account", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    target = next((a for a in items if a["account_id"] == acc["id"]), None)
    assert target is not None
    assert target["income"] >= 800.0
    assert target["expense"] >= 300.0
    assert target["balance"] == target["income"] - target["expense"]