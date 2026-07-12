"""微信 OAuth Connector（预留，待配置 AppID 后实现）

微信开放平台: https://open.weixin.qq.com/
需企业资质 + 审核通过后填 WECHAT_CLIENT_ID/SECRET，再实现下列方法。
微信 OAuth 为两段式（access_token 换 openid），与标准 OAuth2 略有差异。
"""
from .base import OAuthConnector, SocialUserInfo


class WechatConnector(OAuthConnector):
    """微信登录连接器（预留，配置后启用）"""

    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError("微信登录待配置 AppID/Secret 后实现")

    async def exchange_token(self, code: str, redirect_uri: str) -> str:
        raise NotImplementedError("微信登录待实现")

    async def get_userinfo(self, access_token: str) -> SocialUserInfo:
        raise NotImplementedError("微信登录待实现")
