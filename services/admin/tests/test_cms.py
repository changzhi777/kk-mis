"""CMS 内容管理测试：产品 CRUD（A 订制游 + C 权益卡）+ 公开页 + 越权 + 商户 + 素材上传"""


def _create_product(client, h, slug="test-trip", ptype="custom", status="draft"):
    """辅助：创建产品（A 含 custom 扩展 / C 含 pass_config 扩展）"""
    payload = {
        "title": "测试产品",
        "slug": slug,
        "type": ptype,
        "status": status,
        "summary": "测试摘要",
        "highlights": ["亮点一", "亮点二"],
    }
    if ptype == "custom":
        payload["custom"] = {
            "itinerary": [{"day": 1, "title": "抵达", "spots": ["机场"]}],
            "price_mode": "inquiry",
        }
    else:
        payload["pass_config"] = {
            "face_value": "1888",
            "total_worth": "5000",
            "benefits": [{"name": "权益一", "value": "100", "quantity": 2}],
        }
    return client.post("/admin/api/v1/cms/products", json=payload, headers=h).json()


# ===== 产品 CRUD =====
def test_create_custom_product(client, auth_header):
    """创建订制游（含 custom 扩展）"""
    p = _create_product(client, auth_header, slug="custom-1", ptype="custom")
    assert p["id"]
    assert p["type"] == "custom"
    assert p["custom"]["itinerary"][0]["day"] == 1


def test_create_pass_product(client, auth_header):
    """创建权益卡（含 pass_config 扩展）"""
    p = _create_product(client, auth_header, slug="pass-1", ptype="pass")
    assert p["type"] == "pass"
    assert float(p["pass_config"]["face_value"]) == 1888
    assert p["pass_config"]["benefits"][0]["name"] == "权益一"


def test_product_list_filter(client, auth_header):
    _create_product(client, auth_header, slug="list-custom", ptype="custom")
    _create_product(client, auth_header, slug="list-pass", ptype="pass")
    r = client.get("/admin/api/v1/cms/products", params={"type": "pass"}, headers=auth_header)
    assert r.status_code == 200
    slugs = [i["slug"] for i in r.json()["items"]]
    assert "list-pass" in slugs
    assert "list-custom" not in slugs


def test_product_update(client, auth_header):
    p = _create_product(client, auth_header, slug="upd-1")
    r = client.put(
        f"/admin/api/v1/cms/products/{p['id']}",
        json={"title": "新标题", "status": "published"},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "新标题"
    assert body["status"] == "published"
    assert body["published_at"] is not None  # 发布时写入 published_at


def test_product_delete(client, auth_header):
    p = _create_product(client, auth_header, slug="del-1")
    assert client.delete(f"/admin/api/v1/cms/products/{p['id']}", headers=auth_header).status_code == 200
    # 公开页查不到 → 404
    assert client.get("/admin/api/v1/cms/products/del-1").status_code == 404


def test_slug_unique(client, auth_header):
    """slug 重复 → 400"""
    _create_product(client, auth_header, slug="dup-1")
    r = client.post(
        "/admin/api/v1/cms/products",
        json={"title": "T", "slug": "dup-1", "type": "custom"},
        headers=auth_header,
    )
    assert r.status_code == 400


# ===== 公开页 =====
def test_public_page_only_published(client, auth_header):
    """公开页仅返回 published 产品"""
    _create_product(client, auth_header, slug="pub-draft", status="draft")
    assert client.get("/admin/api/v1/cms/products/pub-draft").status_code == 404
    _create_product(client, auth_header, slug="pub-pub", status="published")
    r = client.get("/admin/api/v1/cms/products/pub-pub")  # 无 header
    assert r.status_code == 200
    assert r.json()["slug"] == "pub-pub"


def test_list_requires_auth(client):
    """管理接口无 token → 401（公开页除外）"""
    assert client.get("/admin/api/v1/cms/products").status_code == 401


# ===== 商户 CRUD =====
def test_merchant_crud(client, auth_header):
    m = client.post(
        "/admin/api/v1/cms/merchants",
        json={"name": "测试商户", "address": "上海"},
        headers=auth_header,
    ).json()
    assert m["id"]
    assert len(client.get("/admin/api/v1/cms/merchants", headers=auth_header).json()["items"]) >= 1
    assert client.put(
        f"/admin/api/v1/cms/merchants/{m['id']}", json={"name": "新商户"}, headers=auth_header
    ).json()["name"] == "新商户"
    assert client.delete(f"/admin/api/v1/cms/merchants/{m['id']}", headers=auth_header).status_code == 200


# ===== 素材上传 =====
def test_media_upload_and_serve(client, auth_header):
    """上传素材 + 公开访问"""
    r = client.post(
        "/admin/api/v1/cms/media/upload",
        files={"file": ("test.png", b"\x89PNG\r\n\x1a\nfakepng", "image/png")},
        headers=auth_header,
    )
    assert r.status_code == 200
    asset = r.json()
    assert asset["type"] == "image"
    assert asset["url"].endswith(".png")
    # 公开访问文件（无 header）
    fname = asset["url"].rsplit("/", 1)[-1]
    assert client.get(f"/admin/api/v1/cms/media/file/{fname}").status_code == 200


def test_media_invalid_type(client, auth_header):
    """不支持类型 → 400"""
    r = client.post(
        "/admin/api/v1/cms/media/upload",
        files={"file": ("bad.txt", b"hello", "text/plain")},
        headers=auth_header,
    )
    assert r.status_code == 400


def test_media_path_traversal_blocked(client, auth_header):
    """文件服务防路径遍历"""
    # /file/../../etc/passwd → basename 后非法或 404
    assert client.get("/admin/api/v1/cms/media/file/..%2F..%2Fetc%2Fpasswd").status_code in (400, 404)


# ===== 分类/标签 =====
def test_product_category_tags(client, auth_header):
    """产品含 category/tags + list 按 category 过滤"""
    p = _create_product(client, auth_header, slug="cat-1")
    client.put(
        f"/admin/api/v1/cms/products/{p['id']}",
        json={"category": "海外", "tags": ["海岛", "蜜月"]},
        headers=auth_header,
    )
    r = client.get("/admin/api/v1/cms/products", params={"category": "海外"}, headers=auth_header)
    slugs = [i["slug"] for i in r.json()["items"]]
    assert "cat-1" in slugs
    # 反向：国内分类不含 cat-1
    r2 = client.get("/admin/api/v1/cms/products", params={"category": "国内"}, headers=auth_header)
    assert "cat-1" not in [i["slug"] for i in r2.json()["items"]]


# ===== 询价线索 =====
def test_lead_submit_public(client):
    """公开提交询价线索（无需登录）"""
    r = client.post(
        "/admin/api/v1/cms/leads",
        json={"name": "张三", "phone": "13800138000", "destination": "三亚", "people": 4},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "new"
    assert r.json()["id"]


def test_lead_list_requires_auth(client):
    """admin 线索列表无 token → 401"""
    assert client.get("/admin/api/v1/cms/leads").status_code == 401


def test_lead_status_update(client, auth_header):
    """线索状态流转 new→contacted"""
    lead = client.post(
        "/admin/api/v1/cms/leads", json={"name": "李四", "phone": "13900139000"}, headers=auth_header
    ).json()
    r = client.put(
        f"/admin/api/v1/cms/leads/{lead['id']}/status", json={"status": "contacted"}, headers=auth_header
    )
    assert r.status_code == 200
    assert r.json()["status"] == "contacted"


def test_lead_list_filter(client, auth_header):
    """线索列表按 status 过滤"""
    client.post("/admin/api/v1/cms/leads", json={"name": "王五", "phone": "13700137000"})
    r = client.get("/admin/api/v1/cms/leads", params={"status": "new"}, headers=auth_header)
    assert r.status_code == 200
    assert all(i["status"] == "new" for i in r.json()["items"])


# ===== 订单 + 优惠券 =====
def _create_coupon(client, h, code="TEST10", dtype="percent", value=10):
    return client.post(
        "/admin/api/v1/cms/coupons",
        json={"code": code, "name": "测试券", "discount_type": dtype, "discount_value": value},
        headers=h,
    ).json()


def test_order_create(client, auth_header):
    """权益卡下单（算价：face_value 1888 × quantity）"""
    p = _create_product(client, auth_header, slug="order-1", ptype="pass", status="published")
    r = client.post(
        "/admin/api/v1/cms/orders",
        json={"product_id": p["id"], "quantity": 2, "buyer_name": "买家", "buyer_phone": "13800000000"},
    )
    assert r.status_code == 200
    o = r.json()
    assert o["pay_status"] == "pending"
    assert float(o["original_total"]) == 1888 * 2
    assert float(o["total"]) == float(o["original_total"])  # 无券


def test_order_only_pass(client, auth_header):
    """订制游（custom）不能下单"""
    p = _create_product(client, auth_header, slug="order-custom", ptype="custom")
    r = client.post(
        "/admin/api/v1/cms/orders",
        json={"product_id": p["id"], "quantity": 1, "buyer_name": "x", "buyer_phone": "1"},
    )
    assert r.status_code == 400


def test_order_with_coupon(client, auth_header):
    """下单用优惠券（10% off）"""
    _create_coupon(client, auth_header, code="OFF10", dtype="percent", value=10)
    p = _create_product(client, auth_header, slug="order-coupon", ptype="pass", status="published")
    r = client.post(
        "/admin/api/v1/cms/orders",
        json={"product_id": p["id"], "quantity": 1, "coupon_code": "OFF10", "buyer_name": "x", "buyer_phone": "1"},
    )
    assert r.status_code == 200
    o = r.json()
    assert float(o["discount"]) > 0
    assert float(o["total"]) < float(o["original_total"])


def test_order_pay(client, auth_header):
    """mock 支付 pending→paid + 券 used_count +1"""
    _create_coupon(client, auth_header, code="PAY100", dtype="fixed", value=100)
    p = _create_product(client, auth_header, slug="order-pay", ptype="pass", status="published")
    o = client.post(
        "/admin/api/v1/cms/orders",
        json={"product_id": p["id"], "quantity": 1, "coupon_code": "PAY100", "buyer_name": "x", "buyer_phone": "1"},
    ).json()
    r = client.post(f"/admin/api/v1/cms/orders/{o['id']}/pay")
    assert r.status_code == 200
    assert r.json()["pay_status"] == "paid"
    coupons = client.get("/admin/api/v1/cms/coupons", headers=auth_header).json()["items"]
    assert any(c["code"] == "PAY100" and c["used_count"] == 1 for c in coupons)


def test_coupon_validate(client, auth_header):
    """公开校验券（10% off 1000 → 100）"""
    _create_coupon(client, auth_header, code="VAL10", dtype="percent", value=10)
    r = client.post("/admin/api/v1/cms/coupons/validate", json={"code": "VAL10", "total": "1000"})
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert float(body["discount"]) == 100


def test_coupon_validate_invalid(client):
    """无效券"""
    r = client.post("/admin/api/v1/cms/coupons/validate", json={"code": "NOPE", "total": "100"})
    assert r.json()["valid"] is False


def test_coupon_crud(client, auth_header):
    c = client.post(
        "/admin/api/v1/cms/coupons",
        json={"code": "CRUD1", "name": "C", "discount_type": "fixed", "discount_value": 50},
        headers=auth_header,
    ).json()
    assert c["id"]
    assert client.put(f"/admin/api/v1/cms/coupons/{c['id']}", json={"name": "新"}, headers=auth_header).json()["name"] == "新"
    assert client.delete(f"/admin/api/v1/cms/coupons/{c['id']}", headers=auth_header).status_code == 200


# ===== 浏览埋点 + 评论 + 看板 =====
def test_view_count(client, auth_header):
    """公开页访问 → view_count +1"""
    _create_product(client, auth_header, slug="view-1", ptype="custom", status="published")
    client.get("/admin/api/v1/cms/products/view-1")
    client.get("/admin/api/v1/cms/products/view-1")
    r = client.get("/admin/api/v1/cms/products", params={"type": "custom"}, headers=auth_header)
    item = next(i for i in r.json()["items"] if i["slug"] == "view-1")
    assert item["view_count"] >= 2


def test_review_submit(client, auth_header):
    """公开提交评论 → pending"""
    p = _create_product(client, auth_header, slug="rev-1", status="published")
    r = client.post(
        "/admin/api/v1/cms/reviews",
        json={"product_id": p["id"], "author_name": "用户", "rating": 5, "content": "很棒"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_review_moderate(client, auth_header):
    """admin 审核 pending→approved"""
    p = _create_product(client, auth_header, slug="rev-2", status="published")
    rev = client.post(
        "/admin/api/v1/cms/reviews",
        json={"product_id": p["id"], "author_name": "u", "rating": 4, "content": "好"},
    ).json()
    r = client.put(
        f"/admin/api/v1/cms/reviews/{rev['id']}/status", json={"status": "approved"}, headers=auth_header
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_review_only_approved_in_public(client, auth_header):
    """公开页只显示 approved 评论"""
    p = _create_product(client, auth_header, slug="rev-3", status="published")
    r1 = client.post(
        "/admin/api/v1/cms/reviews",
        json={"product_id": p["id"], "author_name": "a", "rating": 5, "content": "approved-one"},
    ).json()
    client.put(f"/admin/api/v1/cms/reviews/{r1['id']}/status", json={"status": "approved"}, headers=auth_header)
    client.post(
        "/admin/api/v1/cms/reviews",
        json={"product_id": p["id"], "author_name": "b", "rating": 3, "content": "pending-one"},
    )
    pub = client.get("/admin/api/v1/cms/products/rev-3").json()
    assert len(pub["reviews"]) == 1
    assert pub["reviews"][0]["content"] == "approved-one"


def test_dashboard(client, auth_header):
    """admin 看板统计聚合"""
    r = client.get("/admin/api/v1/cms/stats/dashboard", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "products_total" in data
    assert "leads_total" in data
    assert "orders_paid" in data
    assert "revenue" in data
