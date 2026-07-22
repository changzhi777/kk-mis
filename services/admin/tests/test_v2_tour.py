"""V2.0 团期 + 客户预约测试（M3.1：预约团期 b-简，房+车）"""
import uuid


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


def _create_pass(client, admin_h, face_value=100):
    sfx = uuid.uuid4().hex[:6]
    r = client.post(
        "/admin/api/v1/cms/products",
        json={
            "title": f"套餐_{sfx}",
            "slug": f"pkg-{sfx}",
            "type": "pass",
            "status": "published",
            "pass_config": {"face_value": face_value, "total_worth": face_value},
        },
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _create_tour_group(client, admin_h, product_id, capacity=20, hotel=10, car=5):
    r = client.post(
        "/admin/api/v2/tour-groups",
        json={
            "product_id": product_id,
            "title": "国庆团",
            "start_date": "2026-10-01T00:00:00",
            "end_date": "2026-10-07T00:00:00",
            "capacity": capacity,
            "hotel_qty": hotel,
            "car_qty": car,
        },
        headers=admin_h,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_tour_group_create(client, auth_header):
    """超管发布团期（含房+车资源）。"""
    pid = _create_pass(client, auth_header)
    tg = _create_tour_group(client, auth_header, pid)
    assert tg["status"] == "open"
    assert tg["booked"] == 0
    rtypes = {r["resource_type"] for r in tg["resources"]}
    assert rtypes == {"hotel", "car"}


def test_tour_group_list(client, auth_header):
    """列表含 resources 组装。"""
    pid = _create_pass(client, auth_header)
    _create_tour_group(client, auth_header, pid)
    rows = client.get("/admin/api/v2/tour-groups", headers=auth_header).json()
    assert len(rows) >= 1
    assert any(r["resource_type"] == "hotel" for r in rows[-1]["resources"])


def test_reservation_full_flow(client, auth_header):
    """客户预约：扣人数容量 + 房/车资源。"""
    admin = auth_header
    pid = _create_pass(client, admin)
    tg = _create_tour_group(client, admin, pid, capacity=20, hotel=10, car=5)
    customer = _register(client, f"tc_{uuid.uuid4().hex[:6]}")

    res = client.post(
        "/admin/api/v2/reservation",
        json={
            "tour_group_id": tg["id"],
            "people_count": 2,
            "hotel_qty": 1,
            "car_qty": 1,
        },
        headers=customer,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "confirmed"

    # 验证容量 + 资源扣减
    tgs = client.get("/admin/api/v2/tour-groups", headers=admin).json()
    updated = next(t for t in tgs if t["id"] == tg["id"])
    assert updated["booked"] == 2
    hotel = next(r for r in updated["resources"] if r["resource_type"] == "hotel")
    car = next(r for r in updated["resources"] if r["resource_type"] == "car")
    assert hotel["used_qty"] == 1
    assert car["used_qty"] == 1

    # 我的预约
    mine = client.get("/admin/api/v2/reservation", headers=customer).json()
    assert len(mine) == 1
    assert mine[0]["people_count"] == 2


def test_reservation_capacity_exceeded(client, auth_header):
    """人数超容量 → 409。"""
    admin = auth_header
    pid = _create_pass(client, admin)
    tg = _create_tour_group(client, admin, pid, capacity=2)
    customer = _register(client, f"ce_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/reservation",
        json={"tour_group_id": tg["id"], "people_count": 3},
        headers=customer,
    )
    assert r.status_code == 409


def test_reservation_resource_insufficient(client, auth_header):
    """房资源不足 → 409。"""
    admin = auth_header
    pid = _create_pass(client, admin)
    tg = _create_tour_group(client, admin, pid, capacity=20, hotel=1, car=5)
    customer = _register(client, f"ri_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/reservation",
        json={"tour_group_id": tg["id"], "people_count": 1, "hotel_qty": 2},
        headers=customer,
    )
    assert r.status_code == 409


def test_tour_group_create_permission(client, auth_header):
    """非超管发团期 → 403。"""
    pid = _create_pass(client, auth_header)
    plain = _register(client, f"np_{uuid.uuid4().hex[:6]}")
    r = client.post(
        "/admin/api/v2/tour-groups",
        json={
            "product_id": pid,
            "title": "T",
            "start_date": "2026-10-01T00:00:00",
            "end_date": "2026-10-07T00:00:00",
            "capacity": 10,
        },
        headers=plain,
    )
    assert r.status_code == 403
