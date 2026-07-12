"""GitHub OAuth Connector

申请 OAuth App: https://github.com/settings/developers
Authorization callback URL 填: {生产} https://aisport.tech/oa/admin/api/v1/auth/oauth/github/callback
"""
from urllib.parse import urlencode

import httpx

from ..config import settings
from .base import OAuthConnector, SocialUserInfo


class GitHubConnector(OAuthConnector):
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    def __init__(self):
        self.client_id = settings.github_client_id
        self.client_secret = settings.github_client_secret

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_token(self, code: str, redirect_uri: str) -> str:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                self.TOKEN_URL,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        if "access_token" not in data:
            raise ValueError(f"github token 交换失败: {data.get('error_description') or data}")
        return data["access_token"]

    async def get_userinfo(self, access_token: str) -> SocialUserInfo:
        headers = {"Authorization": f"token {access_token}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient(timeout=10) as client:
            user_resp = await client.get(self.USER_URL, headers=headers)
            user_resp.raise_for_status()
            user = user_resp.json()
            email = user.get("email")
            # 邮箱私有时查 /user/emails 取主邮箱
            if not email:
                emails_resp = await client.get(self.EMAILS_URL, headers=headers)
                if emails_resp.status_code == 200:
                    for e in emails_resp.json():
                        if e.get("primary") and e.get("verified"):
                            email = e["email"]
                            break
        return SocialUserInfo(
            provider_uid=str(user["id"]),
            email=email,
            name=user.get("name") or user.get("login"),
        )
