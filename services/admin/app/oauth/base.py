"""OAuth Connector 抽象层

统一第三方 OAuth provider 的对接接口，参考 logto 的 connector 设计：
每 provider 实现 3 个方法 → 主流程对 provider 无感知。
"""
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


class SocialUserInfo(BaseModel):
    """标准化的第三方用户信息（各 connector 输出统一为此结构）"""
    provider_uid: str
    email: Optional[str] = None
    name: Optional[str] = None


class OAuthConnector(ABC):
    """第三方 OAuth 连接器抽象基类"""

    @abstractmethod
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """构造授权页 URL（用户在此登录第三方并授权）"""

    @abstractmethod
    async def exchange_token(self, code: str, redirect_uri: str) -> str:
        """授权码换 access_token"""

    @abstractmethod
    async def get_userinfo(self, access_token: str) -> SocialUserInfo:
        """用 access_token 拉取用户信息（uid/email/name）"""
