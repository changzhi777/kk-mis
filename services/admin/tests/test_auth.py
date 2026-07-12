"""认证关键路径测试"""


def test_login_success(client, auth_header):
    """登录成功 + token 可用"""
    assert "Bearer" in auth_header["Authorization"]


def test_login_wrong_password(client):
    """错误密码 401"""
    r = client.post(
        "/admin/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert r.status_code == 401


def test_me_with_token(client, auth_header):
    """带 token 访问 /me"""
    r = client.get("/admin/api/v1/auth/me", headers=auth_header)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
    assert "super_admin" in r.json()["roles"]


def test_me_without_token(client):
    """无 token 401"""
    r = client.get("/admin/api/v1/auth/me")
    assert r.status_code == 401


def test_register_new_user(client):
    """自助注册：创建成功 + 绑定 staff 角色 + 返回 token"""
    r = client.post(
        "/admin/api/v1/auth/register",
        json={
            "username": "newuser1",
            "password": "test1234",
            "name": "新员工",
            "phone": "13800000000",
        },
    ).json()
    assert r["access_token"]
    assert r["user"]["username"] == "newuser1"
    assert "staff" in r["user"]["roles"]
    # 权限码必须完整（防 get_user_permissions 截断首字符 bug 回归）
    assert "dashboard" in r["user"]["permissions"]
    assert "oa:attendance" in r["user"]["permissions"]


def test_register_duplicate_fails(client):
    """重复用户名注册返回 409"""
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": "admin", "password": "test1234", "name": "重复"},
    )
    assert r.status_code == 409


def test_register_short_password_fails(client):
    """密码不足6位注册失败（422 校验）"""
    r = client.post(
        "/admin/api/v1/auth/register",
        json={"username": "user2", "password": "123", "name": "短密码"},
    )
    assert r.status_code == 422
