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
