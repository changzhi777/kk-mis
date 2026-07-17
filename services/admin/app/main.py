"""kk-cms 企业管理 + 财务 主应用"""
import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request

from . import cache
from .config import settings
from .db import close_db, init_db
from .routes import all_routers

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kk-cms-admin")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("kk-cms Admin 启动中...")
    logger.info(f"  - 监听: {settings.host}:{settings.port}")
    logger.info(f"  - 数据库: {settings.database_display}")
    logger.info(f"  - JWT: {settings.jwt_algorithm} access={settings.access_token_expire}s")
    logger.info("=" * 60)

    # === P0 fail-closed 支付网关注入（2026-07-16 Day 2 缺口 #1 修复）===
    # 风险：若 PAYMENT_PROVIDER=wechat 但启动时未成功构造 wechat gateway，
    #       routes/cms/orders.py::pay_order 会用全局 MockGateway 完成 mock 支付
    #       并写库为真实订单事实 —— silent corruption（资金对账灾难）。
    #
    # 决策：**fail-CLOSED**（拒绝启动，systemd 看到非零退出码 → 告警）。
    #   - 与现有 init_db/cache.init 的 fail-open 不一致，但支付是资金关键路径，
    #     静默降级比显式崩溃更危险（操作员可能不知道生产在用 mock 完成 wechat 订单）。
    #   - 拒绝启动时 ERROR 日志 + traceback 完整写入 journald/systemd journal。
    #   - 如未来需 fail-open（如 dev 模式自动降级），加 APP_ENV != 'production' 分支。
    from .services.payment import build_gateway_from_settings, set_gateway as _set_gw
    try:
        gw = build_gateway_from_settings(settings)
        _set_gw(gw)
        logger.info(
            f"P0 payment gateway initialized: {type(gw).__name__} "
            f"(provider={settings.payment_provider})"
        )
    except Exception as e:
        logger.error(
            f"P0 payment gateway init FAILED: {type(e).__name__}: {e} "
            f"—— 拒绝启动（fail-closed），systemd 将以非零退出码结束，请立即排查。",
            exc_info=True,
        )
        raise  # fail-closed：lifespan 抛出 → 进程退出码非零 → systemd 告警

    try:
        await init_db()
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    await cache.init()  # Redis 缓存层（fail-open，失败不影响启动）

    # ── Office Engine 沙箱（2026-07-17 OFFICE-ENGINE-SANDBOX）──
    # 初始化统一 workspace，挂到 app.state；后台任务定期清理过期临时文件
    from .services.office.workspace import OfficeWorkspace
    app.state.office_workspace = OfficeWorkspace(settings.office_workspace_root)
    app.state.office_cleanup_task = asyncio.create_task(_office_cleanup_loop(app))
    logger.info(
        f"Office workspace ready: root={settings.office_workspace_root} "
        f"tmp_ttl={settings.office_workspace_tmp_ttl}s "
        f"cleanup_interval={settings.office_workspace_cleanup_interval}s"
    )

    # 发卡重试 poller（P0 Day 2：扫描 WebhookRetry 到期任务兜底发卡）
    from .services.payment_fulfillment import start_retry_poller
    poller_task = asyncio.create_task(start_retry_poller())
    yield
    poller_task.cancel()
    # 收尾 office cleanup 后台任务
    cleanup_task = getattr(app.state, "office_cleanup_task", None)
    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    try:
        from .services.notifier import close_client
        await close_client()
        logger.info("notifier client closed")
    except Exception as e:
        logger.warning(f"notifier close_client failed: {e}")
    await cache.close()
    await close_db()
    logger.info("kk-cms Admin 关闭")


async def _office_cleanup_loop(app) -> None:
    """Office 临时文件定期清理后台任务（lifespan 启动）。

    每 ``OFFICE_WORKSPACE_CLEANUP_INTERVAL`` 秒扫一次 workspace，
    删除 mtime 超过 ``OFFICE_WORKSPACE_TMP_TTL`` 秒的 ``_tmp_*`` 文件。
    任何异常仅 warning，不退出循环（资源清理是 best-effort）。
    """
    interval = settings.office_workspace_cleanup_interval or 600
    while True:
        try:
            ws = getattr(app.state, "office_workspace", None)
            if ws is not None:
                ws.cleanup(max_age_seconds=settings.office_workspace_tmp_ttl or 3600)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"office cleanup loop iter failed: {e}")
        await asyncio.sleep(interval)


app = FastAPI(
    title="kk-cms Admin API",
    description="企业管理（RBAC）+ 财务统计",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
_cors_list = (
    ["*"]
    if settings.cors_origins == "*"
    else [o.strip() for o in settings.cors_origins.split(",")]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 注册路由（统一 /admin 前缀，便于 nginx 与会议纪要 /api 分流）
for _r in all_routers:
    app.include_router(_r, prefix="/admin")


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """审计中间件：记录写操作（POST/PUT/PATCH/DELETE）

    MEDIUM 修复（2026-07-16）：
    - 补 PATCH（原漏）
    - 真实 IP 取 X-Forwarded-For（反代后 request.client.host 全是 nginx IP）
    """
    start = time.time()
    response = await call_next(request)
    path = request.url.path
    if (
        request.method in ("POST", "PUT", "PATCH", "DELETE")
        and "/api/v1/" in path
        and "/auth/" not in path  # auth 操作不记日志（含密码等敏感字段）
    ):
        try:
            from .db import SessionLocal
            from .models import AuditLog
            from .security import decode_token

            user_id = None
            auth = request.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                payload = decode_token(auth.split(" ", 1)[1])
                if payload:
                    user_id = int(payload["sub"])
            # 真实 IP：优先 X-Forwarded-For（反代场景），否则回退连接 IP
            xff = request.headers.get("x-forwarded-for", "")
            ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)
            async with SessionLocal() as s:
                s.add(
                    AuditLog(
                        user_id=user_id,
                        method=request.method,
                        path=path,
                        status_code=response.status_code,
                        ip=ip,
                        duration_ms=int((time.time() - start) * 1000),
                    )
                )
                await s.commit()
        except Exception as e:
            logger.warning(f"audit log failed: {e}")
    return response


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "admin",
        "version": "0.1.0",
        "database": settings.database_display,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus 指标端点（含 cos_requests_total / cos_errors_total / cos_duration_seconds）。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {"name": "kk-cms Admin", "version": "0.1.0", "docs": "/docs"}
