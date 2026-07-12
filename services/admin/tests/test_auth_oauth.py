"""OAuth 第三方登录关键路径测试（mock connector，不依赖真实 GitHub）"""
from unittest.mock import patch

from app.oauth.base import SocialUserInfo
from app.routes.auth_oauth import _make_state


class _FakeConnector:
    """模拟 GitHub connector：返回固定的 uid/email/name"""
    def __init__(self, uid="88888", email="gh@test.com", name="GHT"):
        self._info = SocialUserInfo(provider_uid=uid, email=email, name=name)

    def get_authorize_url(self, state, redirect_uri):
        return f"https://github.com/login/oauth/authorize?state={state}"

    async def exchange_token(self, code, redirect_uri):
        return "fake-access-token"

    async def get_userinfo(self, access_token):
        return self._info


def _oauth_callback(client, uid="88888", email="gh@test.com", name="GHT"):
    """触发 GitHub OAuth 回调（follow_redirects=False 看 Location）"""
    state = _make_state("github")
    with patch("app.routes.auth_oauth.get_connector", return_value=_FakeConnector(uid, email, name)):
        return client.get(
            f"/admin/api/v1/auth/oauth/github/callback?code=c&state={state}",
            follow_redirects=False,
        )


def test_oauth_new_user(client, auth_header):
    """新 provider_uid → 自动建 user + 返回 token"""
    r = _oauth_callback(client, uid="77777", email="new@gh.com")
    assert r.status_code == 307
    assert "#t=" in r.headers["location"]
    users = client.get("/admin/api/v1/users", headers=auth_header).json()["items"]
    assert any(u["username"] == "github_77777" for u in users)


def test_oauth_repeat_reuses_account(client):
    """同 provider_uid 二次登录 → 复用账号（不重建）"""
    r1 = _oauth_callback(client, uid="66666", email="r@gh.com")
    r2 = _oauth_callback(client, uid="66666", email="r@gh.com")
    assert r1.status_code == 307 and r2.status_code == 307
    assert "#t=" in r2.headers["location"]


def test_oauth_new_user_gets_staff_role(client):
    """OAuth 新建用户自动绑 staff 角色（基础菜单权限，与注册一致）"""
    from urllib.parse import parse_qs, urlparse

    r = _oauth_callback(client, uid="55555", email="staff@gh.com")
    fragment = urlparse(r.headers["location"]).fragment
    token = parse_qs(fragment)["t"][0]
    me = client.get(
        "/admin/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert "staff" in me["roles"]
    assert "dashboard" in me["permissions"]


def test_oauth_unknown_provider(client):
    """未知 provider → authorize 返回 404"""
    r = client.get("/admin/api/v1/auth/oauth/facebook/authorize")
    assert r.status_code == 404


def test_oauth_bad_state(client):
    """state 篡改 → 回调重定向带 error"""
    with patch("app.routes.auth_oauth.get_connector", return_value=_FakeConnector()):
        r = client.get(
            "/admin/api/v1/auth/oauth/github/callback?code=c&state=tampered",
            follow_redirects=False,
        )
    assert r.status_code == 307
    assert "error=" in r.headers["location"]
