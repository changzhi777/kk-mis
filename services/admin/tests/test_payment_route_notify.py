"""webhook 路由级 HTTP E2E（routes/cms/payments.py::_wechat_notify，2026-07-18）

覆盖路由层职责（网关签名/验签 + confirm DB 逻辑已由 test_wechat_pay_native.py /
test_payment_fulfillment.py 单测覆盖，本文件 monkeypatch 隔离它们）：

- 异常类型 → HTTP 状态码映射：401 验签 / 409 重放 / 400 解析或 out_trade_no 非法 / 503 网关未配置
- 支付冲突 ACK 策略：confirm_payment raise PaymentConflictError → ACK 200 SUCCESS 且不入队
  （防微信重试风暴，P0 CRITICAL 2 修复点；冲突时订单未 paid，入队会卡 retry 5 次转 failed
   而 webhook 已 ACK 微信不重试 → 资金已扣订单悬空）
- 成功链路编排：parse_notify_safe → confirm_payment → enqueue_issue_task → BackgroundTasks
- 非 wechat gateway_name 直接 ignored（mock 链路走 pay_order 同步，webhook 不触发）
"""
import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app import db
from app.models import (
    AssetCardBatch,
    AssetCardType,
    PaymentIdempotency,
    ProductOrder,
    TourPass,
    TourProduct,
    WebhookRetry,
)
from app.routes.cms import payments as pay_mod
from app.services.payment_fulfillment import PaymentConflictError
from app.services.wechat_pay import (
    WechatNotifyDecryptError,
    WechatNotifyError,
    WechatNotifyInvalidJSONError,
    WechatNotifyReplayError,
    WechatNotifySignatureError,
)

NOTIFY_URL = "/admin/api/v1/cms/payments/notify/wechat"


def _notify(out_trade_no="1", amount_total_fen=10000, transaction_id="txn_x"):
    """构造 parse_notify_safe 的成功返回（字段名对齐 WechatNotify DTO 用法）。"""
    return SimpleNamespace(
        out_trade_no=out_trade_no,
        amount_total_fen=amount_total_fen,
        transaction_id=transaction_id,
        resource={"id": "r1"},
    )


def _patch_gateway(monkeypatch, *, parse_ret=None, parse_exc=None, init_exc=None):
    """把路由模块 WechatPayV3Gateway 换成可控桩。

    init_exc 非 None → from_settings() raise（测 503 fail-closed）；
    否则 from_settings() 返回实例，parse_notify_safe 返回 parse_ret 或 raise parse_exc。
    """
    if init_exc is not None:
        def _raise():
            raise init_exc
        monkeypatch.setattr(pay_mod.WechatPayV3Gateway, "from_settings", _raise)
        return
    fake = SimpleNamespace()

    def _parse(headers, raw):
        if parse_exc is not None:
            raise parse_exc
        return parse_ret

    fake.parse_notify_safe = _parse
    monkeypatch.setattr(pay_mod.WechatPayV3Gateway, "from_settings", lambda: fake)


# ── 非 wechat 直接 ignored（mock 链路走 pay_order 同步）──────────────────


def test_notify_non_wechat_ignored(client):
    """gateway_name != wechat → 直接 SUCCESS ignored（不碰网关/DB）。"""
    r = client.post("/admin/api/v1/cms/payments/notify/alipay", json={})
    assert r.status_code == 200
    assert r.json() == {"code": "SUCCESS", "message": "ignored"}


# ── 异常 → 状态码映射 ──────────────────────────────────────────────────


def test_notify_503_gateway_not_configured(client, monkeypatch):
    """网关 fail-closed：from_settings 缺密钥 raise ValueError → 503（P0 #1）。"""
    _patch_gateway(monkeypatch, init_exc=ValueError("missing WECHAT_PAY_API_V3_KEY"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 503


def test_notify_401_signature_invalid(client, monkeypatch):
    """验签失败 → 401（P0 #2 平台证书 + Serial 链路的前置守卫）。"""
    _patch_gateway(monkeypatch, parse_exc=WechatNotifySignatureError("bad sig"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 401


def test_notify_409_replay(client, monkeypatch):
    """Redis 重放检测命中 → 409（P0 #3，同 timestamp+nonce 重复 POST）。"""
    async def _replay(headers):
        raise WechatNotifyReplayError("replay ts+nonce")

    monkeypatch.setattr(pay_mod, "_check_replay", _replay)
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 409


def test_notify_400_invalid_json(client, monkeypatch):
    """回调内容不合法（非 JSON / 缺字段 / 解密失败）→ 400。"""
    _patch_gateway(monkeypatch, parse_exc=WechatNotifyInvalidJSONError("not json"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 400


def test_notify_400_out_trade_no_invalid(client, monkeypatch):
    """parse 成功但 out_trade_no 非数字 → 400（防注入 order_id）。"""
    _patch_gateway(monkeypatch, parse_ret=_notify(out_trade_no="not-a-number"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 400


# ── 冲突 ACK 策略（P0 CRITICAL 2 修复点）──────────────────────────────


def test_notify_200_conflict_acks_without_enqueue(client, monkeypatch):
    """confirm_payment 冲突（金额不符等）→ ACK 200 SUCCESS 且**不入队**。

    冲突时订单仍 pending（confirm 回滚），入队会因状态守卫失败卡 retry 5 次转 failed，
    而 webhook 已 ACK 微信不重试 → 资金已扣订单悬空无人知。正确策略：ACK 防重试风暴
    + 不入队 + 留待人工排查（路由层 rollback 后 return SUCCESS）。
    """
    _patch_gateway(monkeypatch, parse_ret=_notify(out_trade_no="1"))

    async def _conflict(session, n):
        raise PaymentConflictError("amount mismatch")

    monkeypatch.setattr(pay_mod, "confirm_payment", _conflict)

    async def _must_not_enqueue(*a, **kw):
        raise AssertionError("冲突时不应入队发卡任务")

    monkeypatch.setattr(pay_mod, "enqueue_issue_task", _must_not_enqueue)

    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 200
    assert r.json()["code"] == "SUCCESS"


# ── 成功链路编排 ───────────────────────────────────────────────────────


def test_notify_200_success_chain(client, monkeypatch):
    """完整成功链路：parse → confirm → enqueue → BackgroundTasks 注册。

    验证路由正确编排了三个 service 函数 + 参数透传（payment_id / out_trade_no）。
    """
    _patch_gateway(
        monkeypatch,
        parse_ret=_notify(out_trade_no="42", transaction_id="txn_ok"),
    )

    confirmed = {}

    async def _confirm(session, n):
        confirmed["order_id"] = n.order_id
        confirmed["payment_id"] = n.payment_id
        confirmed["amount_fen"] = n.amount_fen

    monkeypatch.setattr(pay_mod, "confirm_payment", _confirm)

    enqueued = {}

    async def _enqueue(session, order_id, payload=None):
        enqueued["order_id"] = order_id
        enqueued["payload"] = payload
        return SimpleNamespace(id=1)

    monkeypatch.setattr(pay_mod, "enqueue_issue_task", _enqueue)

    dispatched = {}

    async def _run(order_id):
        dispatched["order_id"] = order_id

    monkeypatch.setattr(pay_mod, "run_issue_task_async", _run)

    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 200
    assert r.json() == {"code": "SUCCESS", "message": "OK"}

    # confirm 收到路由解析的 order_id / payment_id / 金额（分）
    assert confirmed["order_id"] == 42
    assert confirmed["payment_id"] == "txn_ok"
    assert confirmed["amount_fen"] == 10000
    # enqueue 收到 order_id + notify.resource 作为 payload
    assert enqueued["order_id"] == 42
    assert enqueued["payload"] == {"id": "r1"}
    # BackgroundTasks 注册了发卡任务（TestClient 响应后执行 mock）
    assert dispatched["order_id"] == 42


# ── 异常映射补全：decrypt 子类 + 兜底分支 ──────────────────────────────


def test_notify_400_decrypt_failed(client, monkeypatch):
    """AES-256-GCM 解密失败 → 400（与 invalid_json/missing/invalid_resource 同映射）。"""
    _patch_gateway(monkeypatch, parse_exc=WechatNotifyDecryptError("aes fail"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 400


def test_notify_fallback_custom_subclass(client, monkeypatch):
    """兜底：未在路由显式映射的 WechatNotifyError 子类 → 按 e.http_status 返回。

    路由末尾 `except WechatNotifyError as e: HTTPException(e.http_status)` 兜底，
    保证未来新增异常类型未及时加显式映射时不致 500，仍返回有意义状态码。
    """

    class _CustomNotifyErr(WechatNotifyError):
        http_status = 422  # 非标准，用于验证走兜底 e.http_status 而非硬编码

    _patch_gateway(monkeypatch, parse_exc=_CustomNotifyErr("future case"))
    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 422


# ── 真 DB 端到端：seed 订单 → webhook → 真 confirm_payment 落库 ────────


async def _seed_pending_order() -> int:
    """通过 app SessionLocal 在 test.db seed 一个 pending 订单，返回 order_id。"""
    async with db.SessionLocal() as s:
        ct = AssetCardType(name="VIP-R", type="vip", face_value=100, unit_price=100)
        s.add(ct)
        await s.flush()
        batch = AssetCardBatch(
            type_id=ct.id, name="BR", quantity=10, generated=0, status="active"
        )
        s.add(batch)
        await s.flush()
        p = TourProduct(
            title="R卡", slug=f"r-{ct.id}-{batch.id}", type="pass",
            status="published", card_type_id=ct.id,
        )
        s.add(p)
        await s.flush()
        s.add(TourPass(product_id=p.id, face_value=100))
        await s.flush()
        o = ProductOrder(
            product_id=p.id, quantity=1, unit_price=100,
            original_total=100, discount=0, total=100,
            buyer_name="R", buyer_phone="13800000000", pay_status="pending",
        )
        s.add(o)
        await s.flush()
        await s.commit()
        return o.id


def test_notify_real_confirm_persists_paid(client, monkeypatch):
    """真 DB 端到端：seed pending 订单 → webhook → 真 confirm_payment 落库。

    不 mock confirm_payment，验证路由→app session→confirm→test.db 完整链路：
    order pending→paid + transaction_id 双写 + PaymentIdempotency 幂等记录
    + enqueue_issue_task 真落 WebhookRetry。confirm 的金额/幂等/券逻辑由
    test_payment_fulfillment.py 单测覆盖，本测试只钉"路由层把请求串到 DB 落库"。
    """
    order_id = asyncio.run(_seed_pending_order())

    notify = SimpleNamespace(
        out_trade_no=str(order_id), amount_total_fen=10000,
        transaction_id="real_txn", resource={"id": "rr"},
    )
    _patch_gateway(monkeypatch, parse_ret=notify)

    async def _run(oid):  # 避免 BackgroundTasks 真跑独立 session 发卡
        pass

    monkeypatch.setattr(pay_mod, "run_issue_task_async", _run)

    r = client.post(NOTIFY_URL, json={})
    assert r.status_code == 200
    assert r.json()["code"] == "SUCCESS"

    async def _verify():
        async with db.SessionLocal() as s:
            o = await s.get(ProductOrder, order_id)
            assert o.status == "paid"
            assert o.pay_status == "paid"  # LEGACY 双写
            assert o.transaction_id == "real_txn"
            idem = (
                await session_execute_count(s, PaymentIdempotency, PaymentIdempotency.order_id == order_id)
            )
            assert idem == 1
            jobs = (
                await session_execute_count(s, WebhookRetry, WebhookRetry.order_id == order_id)
            )
            assert jobs == 1

    asyncio.run(_verify())


async def session_execute_count(s, model, where):
    """小工具：count 查询（抽出避免 _verify 闭包里 await 表达式过长）。"""
    return (await s.execute(select(func.count(model.id)).where(where))).scalar_one()
