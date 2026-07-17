# P0 微信支付灰度 + 生产 alembic 收敛 Runbook

> 产物：2026-07-17 第八轮·实施续（commit `4194544` alembic / `1340df6` tripgen / `418692a` wechat_pay P0#5 / `fb47a49` mch_serial_no fix）
> **代码侧全就绪**，本文档是"密钥/生产到位后怎么跑"的执行手册。

---

## Part A：微信支付 P0 灰度上线

### A0. 前置条件（代码侧已就绪）

| 能力 | commit | 状态 |
|------|--------|------|
| `WechatPayV3Gateway.pay/refund/query`（手写 V3 签名，不黑盒 SDK） | `418692a` | ✅ |
| `mch_serial_no` 配置链（字段+校验+注入+`.env.example`） | `fb47a49` | ✅ |
| fail-closed lifespan（缺密钥拒绝启动，systemd 非零退出） | `3b82c55` | ✅ |
| X.509 平台证书 + `Wechatpay-Serial` 验签（支持轮换） | `308199f` | ✅ |
| `parse_notify_safe` 安全 4xx（7 异常类 + Redis NX 重放检测） | `45ac695` | ✅ |
| 异常持久化 + `SKIP LOCKED` 租约 + 3 Prometheus 指标 | `08835b7` | ✅ |
| 回调幂等 + 多卡履约 `issue_order_cards` + 重试 poller | Day 2 | ✅ |

**测试基线**：463 passed / 0 failed / 6 skipped（含 `test_wechat_pay_native.py` 11 项自签 RSA + 自签 X.509 平台证书覆盖签名/验签/解析/fail-closed）。

### A1. 配置 `.env`（7 项）

```env
PAYMENT_PROVIDER=wechat
WECHAT_PAY_MCH_ID=<商户号>
WECHAT_PAY_APP_ID=<应用 AppID>
WECHAT_PAY_API_V3_KEY=<32 字节 APIv3 密钥>
WECHAT_PAY_MCH_SERIAL_NO=<商户证书序列号>
WECHAT_PAY_PLATFORM_CERT_PATH=/opt/kk-mis/certs/wechat/platform.pem
WECHAT_PAY_MCH_PRIVATE_KEY_PATH=/opt/kk-mis/certs/wechat/mch_private.pem
WECHAT_PAY_NOTIFY_URL=https://nanoai.fun/oa/admin/api/v1/cms/payments/notify/wechat
```

- **`MCH_SERIAL_NO`**：微信商户平台 → API 安全 → API 证书 → 证书信息（**商户自己的证书序列号**，不是微信平台证书序列号；请求签名 Authorization 头用它告诉微信"用哪个商户证书验签我的请求"）
- **`PLATFORM_CERT_PATH`**：微信支付**平台**证书（X.509 PEM）。用 APIv3 密钥调 `GET /v3/certificates` 下载。多证书轮换期用 `WECHAT_PAY_PLATFORM_CERTS=SERIAL1:/p1.pem,SERIAL2:/p2.pem` 或 `WECHAT_PAY_PLATFORM_CERT_DIR=/path/`
- **`MCH_PRIVATE_KEY_PATH`**：商户 API 证书私钥（`apiclient_key.pem`）

### A2. 启动验证（fail-closed）

```bash
sudo systemctl restart kk-mis-admin
journalctl -u kk-mis-admin -n 50 --no-pager | grep -i "payment gateway"
# 期望：P0 payment gateway initialized: WechatPayV3Gateway
```

**故意填错验 fail-closed**（上线前必做一次）：把 `WECHAT_PAY_API_V3_KEY` 改成 31 字节（非法长度），重启应：
- log：`P0 payment gateway init FAILED: ValueError ... 拒绝启动（fail-closed）`
- systemd：非零退出码 → restart loop → 告警可见

**若降级到 MockGateway 说明 fail-closed 失效 → 禁止继续**（资金 silent corruption 风险）。

### A3. 小额灰度（1 分钱真单）

1. 后台建一个 0.01 元测试权益卡产品（关联 `card_type_id` + active batch）
2. C 端下单 → `POST /admin/api/v1/cms/orders/{id}/pay` → 返回 `code_url`（Native 预下单）
3. `code_url` 生成二维码 → 手机微信扫码 → 支付 1 分钱
4. **验 webhook 回调链路**：
   - admin log：`parse_notify_safe` 成功 → `confirm_payment`（金额分校验 + 订单行锁 + 状态 paid）→ `issue_order_cards`（发卡）
   - 订单状态：`pending → paid → fulfilled`
   - DB 抽查：`cms_payment_idempotency` 有幂等记录；`cms_order_card` 有发卡关联；`cms_product_order.status=paid/fulfilled`
5. `gateway.query(order_id)` 确认 `trade_state=SUCCESS`
6. **验重放**：同 `timestamp+nonce` 再 POST webhook → 409（Redis NX 拦截）

**任一步失败**：查 `cms_payment_exception_event` 表（`severity=warning|critical`）+ Prometheus 指标（`payment_*` 系列）。

### A4. 全量放开

A3 全绿 → 移除测试产品限制 → 开放正常商品 → 观察 24h `cms_payment_exception_event` 无 critical。

### A5. 回滚

紧急回 mock：`PAYMENT_PROVIDER=mock` 重启（fail-closed 对 mock 不触发）。已发生的微信交易不逆转（资金已到账），仅新订单走 mock。

---

## Part B：生产 alembic schema 收敛（PROD-SCHEMA-DRIFT）

### B1. SSH 生产评估（必先）

```bash
ssh root@43.129.201.118
cd /opt/kk-mis/services/admin
PYTHONPATH=. .venv/bin/alembic current    # 看生产 alembic_version 状态
PYTHONPATH=. .venv/bin/alembic heads      # 应 1 head = 20260717_cms_media_asset_storage_cols
```

看 `alembic current` 输出决策：
- **输出某 revision**（如 `20260715_cms_payment_exception_event_p1 (head)`）→ 生产已跑过 alembic，走 **B2-upgrade**
- **空 / 无 alembic_version 表** → 生产一直靠 `create_all`，走 **B2-stamp**

### B2. 决策路径

**路径 1（生产已有 alembic 历史）→ 直接 upgrade**：
```bash
PYTHONPATH=. .venv/bin/alembic upgrade head
# storage_cols 幂等：生产 cms_media_asset 已有 4 列（2026-07-16 手工 ALTER）
# → inspector checkfirst 跳过，仅更新版本标记到 storage_cols
```

**路径 2（生产靠 create_all，无 alembic 历史）→ 先评估再 stamp**：
1. dump 生产 schema 对比模型，确认都已存在：
   - P0 三表：`cms_payment_idempotency` / `cms_webhook_retry` / `cms_order_card`
   - `cms_payment_exception_event`（08835b7 新增）
   - `cms_media_asset` 4 列（storage_backend/storage_key/etag/content_type）
   - `cms_product_order.status`（7 状态机字段）
2. **全在** → `PYTHONPATH=. .venv/bin/alembic stamp head`（标记生产已到最新，不执行 DDL）
3. **缺表/列** → `PYTHONPATH=. .venv/bin/alembic upgrade head`（建缺的；storage_cols 幂等加 4 列）

### B3. 验证收敛

```bash
PYTHONPATH=. .venv/bin/alembic current
# 期望：20260717_cms_media_asset_storage_cols (head)

# PG 抽查 cms_media_asset 4 列
psql -U postgres -d kk_admin -c "\d cms_media_asset"
```

### B4. 回滚（downgrade）

```bash
PYTHONPATH=. .venv/bin/alembic downgrade 20260715_cms_payment_exception_event_p1
# 删 cms_media_asset 4 列（PG 直接 DROP / SQLite batch 重建）
# ⚠️ 生产回滚前确认无业务依赖这 4 列（Storage 抽象层在用 storage_backend/storage_key）
```

---

## 关联

- P0 方案：`cms-payments-webhook-p0.md`
- P0 Day 2 实施：memory `project-p0-day2-implementation-2026-07-16.md`
- 本轮实施：memory `project-round8-implementation-2026-07-17.md`
- 测试：`tests/test_wechat_pay_native.py`（11 项）+ `tests/test_tripgen.py`（+5）+ alembic revision 临时库幂等验证
