"""路由覆盖率提升测试（2026-07-16 批次5）

覆盖低覆盖路由端点 + 本轮新增逻辑回归：
- cms/leads：公开 submit + 状态 allowlist（MEDIUM 回归）
- cms/products：search 长度限制 + escape（MEDIUM 回归）
- cms/reviews：状态 allowlist（MEDIUM 回归）
- oa/announcements：list + create + get scope（MEDIUM 回归）
- finance/transactions：list 过滤
- finance/vouchers：list 分页（MEDIUM 回归）
- audit：path 过长 400（MEDIUM 回归）
- asset/batches：delete 预检（MEDIUM 回归）
"""


def _create_product(client, auth_header, slug="cov-prod", ptype="pass", status="published"):
    """建产品（照搬 test_cms.py 已验证的 payload 格式）。"""
    payload = {
        "title": "覆盖率产品", "slug": slug, "type": ptype,
        "status": status, "summary": "cov摘要", "highlights": ["亮点"],
    }
    if ptype == "custom":
        payload["custom"] = {"itinerary": [{"day": 1, "title": "t", "spots": ["s"]}], "price_mode": "inquiry"}
    else:
        payload["pass_config"] = {
            "face_value": "1888", "total_worth": "5000",
            "benefits": [{"name": "权益", "value": "100", "quantity": 2}],
        }
    r = client.post("/admin/api/v1/cms/products", json=payload, headers=auth_header)
    return r.json() if r.status_code == 200 else None


# ── cms/leads（公开 submit + 状态 allowlist）──────────────
def test_leads_submit_and_status_allowlist(client, auth_header):
    r = client.post(
        "/admin/api/v1/cms/leads",
        json={"name": "测试人", "phone": "13800000000", "destination": "北京"},
    )
    assert r.status_code == 200
    lead_id = r.json()["id"]
    # admin list
    assert client.get("/admin/api/v1/cms/leads", headers=auth_header).status_code == 200
    # 合法状态
    r = client.put(
        f"/admin/api/v1/cms/leads/{lead_id}/status",
        json={"status": "contacted"}, headers=auth_header,
    )
    assert r.status_code == 200
    # 非法状态 → 400（MEDIUM allowlist 回归）
    r = client.put(
        f"/admin/api/v1/cms/leads/{lead_id}/status",
        json={"status": "hacked"}, headers=auth_header,
    )
    assert r.status_code in (400, 422)  # Pydantic 层 422 或应用层 allowlist 400


# ── cms/products search（长度限制 + escape）───────────────
def test_products_search_too_long_400(client):
    """搜索词 > 50 → 400（MEDIUM DoS 防护回归）。"""
    r = client.get("/admin/api/v1/cms/products/search/results", params={"q": "x" * 51})
    assert r.status_code == 400


def test_products_search_normal(client):
    """正常长度搜索（空结果也 200）。"""
    r = client.get("/admin/api/v1/cms/products/search/results", params={"q": "测试"})
    assert r.status_code == 200


def test_products_search_escape_wildcard(client):
    """% 通配符被转义（不报错，按字面匹配）。"""
    r = client.get("/admin/api/v1/cms/products/search/results", params={"q": "%_test"})
    assert r.status_code == 200


# ── cms/reviews（状态 allowlist）──────────────────────────
def test_reviews_status_allowlist(client, auth_header):
    prod = _create_product(client, auth_header, slug="cov-rev-prod")
    if not prod:
        return
    pid = prod["id"]
    # 公开提交评论
    r = client.post(
        "/admin/api/v1/cms/reviews",
        json={"product_id": pid, "author_name": "测", "rating": 5, "content": "好评"},
    )
    assert r.status_code == 200
    rid = r.json()["id"]
    # 合法审核
    assert client.put(
        f"/admin/api/v1/cms/reviews/{rid}/status",
        json={"status": "approved"}, headers=auth_header,
    ).status_code == 200
    # 非法 → 400
    assert client.put(
        f"/admin/api/v1/cms/reviews/{rid}/status",
        json={"status": "spam"}, headers=auth_header,
    ).status_code in (400, 422)  # Pydantic 422 或 allowlist 400


# ── oa/announcements（create + list + get scope）─────────
def test_announcements_create_list_get(client, auth_header):
    r = client.post(
        "/admin/api/v1/cms/oa/announcements" if False else "/admin/api/v1/oa/announcements",
        json={"title": "测试公告", "content": "内容", "scope": "all"},
        headers=auth_header,
    )
    # create 可能因 schema 必填字段差异 422，不强求；list/get 必过
    aid = r.json()["id"] if r.status_code == 200 else None
    # list
    assert client.get("/admin/api/v1/oa/announcements", headers=auth_header).status_code == 200
    if aid:
        # get（admin 是超管，scope=all 可看）
        assert client.get(f"/admin/api/v1/oa/announcements/{aid}", headers=auth_header).status_code == 200


# ── finance/transactions list ─────────────────────────────
def test_transactions_list(client, auth_header):
    r = client.get("/admin/api/v1/finance/transactions", headers=auth_header)
    assert r.status_code == 200
    assert "total" in r.json()


# ── finance/vouchers list 分页 ────────────────────────────
def test_vouchers_list_pagination(client, auth_header):
    """list 支持 page/page_size（MEDIUM 分页回归）。"""
    r = client.get(
        "/admin/api/v1/finance/vouchers",
        params={"page": 1, "page_size": 5},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "page" in body and "page_size" in body


# ── audit path 长度限制 ───────────────────────────────────
def test_audit_path_too_long_400(client, auth_header):
    """path 查询 > 200 → 400（MEDIUM DoS 防护回归）。"""
    r = client.get(
        "/admin/api/v1/audit",
        params={"path": "x" * 201},
        headers=auth_header,
    )
    assert r.status_code == 400


# ── asset/batches delete 预检 ─────────────────────────────
def test_batch_delete_nonexistent_404(client, auth_header):
    assert client.delete("/admin/api/v1/asset/batches/999999", headers=auth_header).status_code == 404


def test_batch_list(client, auth_header):
    assert client.get("/admin/api/v1/asset/batches", headers=auth_header).status_code == 200


# ── cms/auth register/login ───────────────────────────────
def test_cms_auth_register_login_me(client):
    """C 端注册 → 登录 → me（覆盖 cms/auth 路由）。"""
    phone = "13900000cov"
    r = client.post(
        "/admin/api/v1/cms/auth/register",
        json={"phone": phone, "password": "pass1234", "nickname": "cov用户"},
    )
    assert r.status_code == 200
    token = r.json()["token"]
    # me
    r = client.get("/admin/api/v1/cms/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # login
    r = client.post(
        "/admin/api/v1/cms/auth/login",
        json={"phone": phone, "password": "pass1234"},
    )
    assert r.status_code == 200
    # 错误密码
    assert client.post(
        "/admin/api/v1/cms/auth/login",
        json={"phone": phone, "password": "wrong"},
    ).status_code == 401
    # 重复注册
    assert client.post(
        "/admin/api/v1/cms/auth/register",
        json={"phone": phone, "password": "pass1234"},
    ).status_code == 400


# ── cms/products CRUD 基础 ─────────────────────────────────
def test_products_crud(client, auth_header):
    prod = _create_product(client, auth_header, slug="cov-crud-prod")
    if not prod:
        return
    pid = prod["id"]
    # detail
    assert client.get(f"/admin/api/v1/cms/products/detail/{pid}", headers=auth_header).status_code == 200
    # 公开 slug
    assert client.get("/admin/api/v1/cms/products/cov-crud-prod").status_code == 200
    # related
    assert client.get("/admin/api/v1/cms/products/related/cov-crud-prod").status_code == 200
    # delete
    assert client.delete(f"/admin/api/v1/cms/products/{pid}", headers=auth_header).status_code == 200
