"""OAuth Connector 注册表（provider 名 → connector 实例）

新增 provider：写 connector 类 + 这里注册一条即可，主流程不动（开闭原则）。
"""
from .github import GitHubConnector
from .wechat import WechatConnector

_CONNECTORS = {
    "github": GitHubConnector(),
    "wechat": WechatConnector(),
}


def get_connector(provider: str) -> object:
    """获取 connector；未知 provider 抛 KeyError（路由层转 404）"""
    c = _CONNECTORS.get(provider)
    if c is None:
        raise KeyError(provider)
    return c


def supported_providers() -> list[str]:
    return list(_CONNECTORS.keys())
