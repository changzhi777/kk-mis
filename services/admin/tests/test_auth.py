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
