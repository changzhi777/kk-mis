# OAuth 第三方登录扩展（参考 logto connector 模式）

## 上下文
kk-mis 当前仅支持用户名/密码 + 自助注册。需扩展支持第三方 OAuth 登录（GitHub 先打通，微信预留）。
- 路径：B（参考 logto connector 设计，自建内嵌，复用现有 JWT+User）
- 无新依赖（httpx 已有）
- 账号绑定：① social_account 命中→直登 ② 同 email→绑现有 ③ 都无→新建（username=`gh_<uid>`）

## 执行步骤（15 步）
1. `models/social.py` SocialAccount 表 + `models/__init__` 导出
2. `config.py` Settings 加 github/wechat OAuth 配置
3. `oauth/base.py` SocialUserInfo + OAuthConnector 抽象基类
4. `oauth/github.py` GitHubConnector（authorize/token/userinfo）
5. `oauth/wechat.py` WechatConnector（预留 NotImplementedError）
6. `oauth/registry.py` get_connector 映射
7. `routes/auth_oauth.py`：authorize（302+state JWT）/callback（验 state→换 token→userinfo→查建绑→签 JWT→302 前端#token）
8. `main.py`/`routes/__init__` 注册路由
9. `stores/user.ts` 抽 applyTokenData（DRY）
10. `views/oauth/Callback.vue` 解析 hash token 入系统
11. `router/index.ts` 加 /oauth/callback（public）
12. `Login.vue`/`Register.vue` 加 GitHub 登录按钮
13. `tests/test_auth_oauth.py` mock connector 3 用例
14. **[阻塞-用户操作]** GitHub OAuth App 申请 + Client ID/Secret
15. 本地验证 + scp 部署 + 浏览器实走

## 关键设计
- state：复用 security 的 jwt.encode，payload `{sub:provider, type:oauth_state, exp:600s}`，无状态免 Redis
- token 传递：URL hash（`#t=&r=`），不进 server log
- connector 统一接口：get_authorize_url/exchange_token/get_userinfo

## 阻塞项
步骤14 需用户去 GitHub 申请 OAuth App（callback URL: `https://aisport.tech/oa/admin/api/v1/auth/oauth/github/callback`）
