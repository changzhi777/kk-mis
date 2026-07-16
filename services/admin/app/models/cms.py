"""CMS 内容管理模型：旅游产品（订制游 A + 权益卡 C）+ 素材库 + 合作商户

2026-07-14 新增（基于 docs/cms-content-module-research.md）：
- TourProduct 统一抽象，type 区分 custom(订制游) / pass(权益卡)
- TourCustom / TourPass 分别为 A/C 扩展（product_id 关联）
- MediaAsset 素材库（图/视频）
- Merchant 合作商户（权益卡 C 用）
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property

from ..utils import utcnow
from .base import Base
from .enterprise import pk


class MediaAsset(Base):
    """素材库（图片/视频）

    2026-07-14 引入 Storage 抽象层（Phase 0）：
    - storage_backend: 'local' | 'cos'
    - storage_key: ObjectKey.value（如 'cms/media/abc.png'）
    - etag: COS ETag；local 用 UUID 占位
    - content_type: MIME（推荐存）
    老记录 defaults 'local' / None 兼容。
    """

    __tablename__ = "cms_media_asset"

    id = pk()
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False)  # image|video
    url = Column(String(500), nullable=False)
    size = Column(Integer, default=0)  # 字节
    alt = Column(String(200), nullable=True)  # 图片说明
    tags = Column(JSON, default=list)  # 标签列表
    uploaded_by = Column(BigInteger, nullable=True)
    # ── Storage 抽象层新增字段（2026-07-14）──
    storage_backend = Column(String(20), default="local", nullable=False)  # 'local' | 'cos'
    storage_key = Column(String(512), nullable=True)  # ObjectKey.value；老数据为 NULL
    etag = Column(String(64), nullable=True)  # COS ETag / MD5；local 用 UUID 占位
    content_type = Column(String(64), default="image/png", nullable=False)
    created_at = Column(DateTime, default=utcnow)


class Merchant(Base):
    """合作商户（权益卡 C 用）"""

    __tablename__ = "cms_merchant"

    id = pk()
    name = Column(String(100), nullable=False)
    logo = Column(String(500), nullable=True)
    address = Column(String(300), nullable=True)
    contact = Column(String(100), nullable=True)
    benefit_desc = Column(Text, nullable=True)  # 权益内容描述
    status = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class TourProduct(Base):
    """旅游产品（统一抽象，type 区分订制游 / 权益卡）

    公开介绍页 /product/{slug} 读此表 + 对应 type 扩展表。
    """

    __tablename__ = "cms_tour_product"

    id = pk()
    title = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False, index=True)  # URL 标识
    type = Column(String(20), nullable=False)  # custom(订制游) | pass(权益卡)
    destination = Column(String(100), nullable=True)  # 目的地
    theme = Column(String(50), nullable=True)  # 主题：海岛/亲子/商务/蜜月...
    category = Column(String(50), nullable=True, index=True)  # 分类：国内/海外/周边
    tags = Column(JSON, default=list)  # 标签列表
    cover_image = Column(String(500), nullable=True)  # 封面图 URL
    gallery = Column(JSON, default=list)  # 图集 URL 列表
    video_url = Column(String(500), nullable=True)
    summary = Column(String(500), nullable=True)  # 摘要
    content = Column(Text, nullable=True)  # 富文本 HTML（编辑器输出）
    highlights = Column(JSON, default=list)  # 亮点列表 ["", ""]
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft|published|archived
    sort = Column(Integer, default=0)
    view_count = Column(Integer, default=0)  # 浏览量（公开页访问 +1）
    card_type_id = Column(BigInteger, ForeignKey("asset_card_type.id"), nullable=True)  # 关联 asset 卡券类型（pass 产品支付后自动发卡）
    seo_title = Column(String(200), nullable=True)
    seo_description = Column(String(500), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class TourCustom(Base):
    """订制游扩展（A）：行程 / 服务流程 / 报价 / 顾问"""

    __tablename__ = "cms_tour_custom"

    id = pk()
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=False, index=True)
    itinerary = Column(JSON, default=list)  # [{day,title,transport,spots[],meals,hotel,description}]
    service_flow = Column(JSON, default=list)  # 服务流程 [{step,title,description}]
    price_mode = Column(String(20), default="inquiry")  # inquiry(询价) | tier(阶梯)
    price_tiers = Column(JSON, default=list)  # 阶梯报价 [{label,price,description}]
    consultant_ids = Column(JSON, default=list)  # 顾问 user_id 列表


class TourPass(Base):
    """权益卡扩展（C）：权益清单 / 商户 / 卡面值 / 使用规则"""

    __tablename__ = "cms_tour_pass"

    id = pk()
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=False, index=True)
    face_value = Column(Numeric(12, 2), default=0)  # 卡面值
    total_worth = Column(Numeric(12, 2), default=0)  # 权益总价（对比用）
    valid_period = Column(String(100), nullable=True)  # 有效期描述
    usage_rules = Column(Text, nullable=True)  # 使用规则
    benefits = Column(JSON, default=list)  # [{name,value,quantity,merchant_id}]
    merchant_ids = Column(JSON, default=list)  # 合作商户 id 列表


class InquiryLead(Base):
    """询价线索（订制游 A：终端用户公开提交，admin 跟进）

    公开提交（POST /leads，无需登录）→ admin 列表/状态流转（new→contacted→converted/closed）。
    """

    __tablename__ = "cms_inquiry_lead"

    id = pk()
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=True, index=True)
    name = Column(String(50), nullable=False)  # 联系人
    phone = Column(String(30), nullable=False)  # 电话
    wechat = Column(String(50), nullable=True)  # 微信（可选）
    destination = Column(String(100), nullable=True)  # 意向目的地
    travel_date = Column(String(50), nullable=True)  # 出行日期
    people = Column(Integer, nullable=True)  # 人数
    budget = Column(String(50), nullable=True)  # 预算
    remark = Column(Text, nullable=True)  # 备注/需求
    status = Column(String(20), default="new", nullable=False, index=True)  # new/contacted/converted/closed
    created_at = Column(DateTime, default=utcnow)


class ProductOrder(Base):
    """权益卡订单（C：公开下单，mock 支付，运营后续发卡）

    下单时锁定单价（取自 product.pass_config.face_value），支付成功标记 paid。
    不自动发真实 asset 卡（订单记录，运营后续发卡，避免接 asset 发卡流程的复杂性）。

    === P0 CMS 真支付 状态机迁移（2026-07-15，详见 docs/cms-payments-webhook-p0.md）===

    **status 字段（NEW）**：7 状态机
        pending            下单后未支付
        paid               支付成功（fact only，履约未开始）
        card_issuing       履约中（发卡进行中）
        fulfilled          履约完成（卡已发到买家）
        failed             履约失败（发卡异常，待人工）
        cancelled          订单取消（用户/运营取消）
        refunded           已退款

    **pay_status 字段（LEGACY）**：保留兼容窗口
        pending|paid|cancelled
        ⚠️ 不再写入。保留字段直到 2026-09 前端全部切读 `status` 后由 Day 1.2 后期
        单独 migration 移除（约 2-3 个月窗口）。

    **effective_status 属性**：API 响应统一返回新 status；历史客户端按
        pay_status 读数据时可平滑过渡。回退映射：pending→pending,
        paid→paid, cancelled→cancelled。

    **is_paid 属性**：用于业务判断"是否已支付事实"，覆盖 paid/issuing/fulfilled/
        failed/refunded（即一切 post-paid 状态）。
    """

    __tablename__ = "cms_product_order"

    id = pk()
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Numeric(12, 2), default=0)  # 锁定单价
    original_total = Column(Numeric(12, 2), default=0)  # unit_price * quantity
    discount = Column(Numeric(12, 2), default=0)  # 优惠金额
    total = Column(Numeric(12, 2), default=0)  # 实付
    coupon_id = Column(BigInteger, nullable=True)
    coupon_code = Column(String(50), nullable=True)  # 冗余记录
    buyer_name = Column(String(50), nullable=False)
    buyer_phone = Column(String(30), nullable=False)
    remark = Column(Text, nullable=True)
    # ── LEGACY 字段（兼容窗口保留，不再写入，2026-09 移除） ──
    pay_status = Column(String(20), default="pending", nullable=False, index=True)  # LEGACY: pending|paid|cancelled
    # ── NEW 字段（P0 Day 1.2.1 引入） ──
    status = Column(String(20), default="pending", nullable=True, index=True)  # NEW: pending|paid|card_issuing|fulfilled|failed|cancelled|refunded
    referrer_agent_id = Column(BigInteger, nullable=True, index=True)  # A2 推荐代理（来自推广码）
    referral_commission = Column(Numeric(12, 2), default=0)  # A2 推荐返佣（total * 5%）
    paid_at = Column(DateTime, nullable=True)
    issued_card_no = Column(String(32), nullable=True)  # 支付后发的卡号（明文一次性给买家）
    issued_card_password = Column(String(10), nullable=True)  # 卡密码（明文一次性）
    transaction_id = Column(String(100), nullable=True)  # 支付网关交易号
    created_at = Column(DateTime, default=utcnow)

    @hybrid_property
    def effective_status(self) -> str:
        """API 兼容：返回新的 status 字段；旧 pay_status 客户端平滑过渡。

        优先级：status 优先 → fallback 到 pay_status 映射 → 默认 'pending'。
        """
        status = getattr(self, "status", None)
        if status:
            return status
        # LEGACY fallback
        mapping = {
            "pending": "pending",
            "paid": "paid",
            "cancelled": "cancelled",
        }
        return mapping.get(self.pay_status, "pending")

    @hybrid_property
    def is_paid(self) -> bool:
        """True if order has been paid (any post-paid state).

        用于业务判断"是否已支付事实"，覆盖：
        paid / card_issuing / fulfilled / failed / refunded
        （pending / cancelled 不算 paid）
        """
        return self.effective_status in (
            "paid", "card_issuing", "fulfilled", "failed", "refunded",
        )


class Coupon(Base):
    """优惠券/折扣码（percent 百分比 / fixed 固定金额）"""

    __tablename__ = "cms_coupon"

    id = pk()
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    discount_type = Column(String(20), nullable=False)  # percent|fixed
    discount_value = Column(Numeric(12, 2), nullable=False)  # percent: 0-100；fixed: 金额
    min_total = Column(Numeric(12, 2), default=0)  # 满减门槛
    max_uses = Column(Integer, default=0)  # 0=不限
    used_count = Column(Integer, default=0)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class Review(Base):
    """产品评论/评价（公开提交，admin 审核）

    状态：pending（待审）→ approved（通过，公开页展示）/ rejected（拒绝）
    """

    __tablename__ = "cms_review"

    id = pk()
    product_id = Column(BigInteger, ForeignKey("cms_tour_product.id"), nullable=False, index=True)
    author_name = Column(String(50), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5 星
    content = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending|approved|rejected
    created_at = Column(DateTime, default=utcnow)


class EndUser(Base):
    """C 端终端用户（公开页注册/登录，独立于 admin RBAC）

    与 admin User 区分：admin 是后台管理用户（RBAC），EndUser 是 C 端消费者。
    JWT 用 type=end_user 区分。
    """

    __tablename__ = "cms_end_user"

    id = pk()
    phone = Column(String(30), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utcnow)


class PaymentIdempotency(Base):
    """支付请求幂等日志（P0 Day 1.1，表 cms_payment_idempotency）

    记录每个支付请求的 request/response；靠 (payment_provider, payment_id) 部分
    唯一索引防重放（payment_id 为 NULL 的 mock 行不受约束，mock 模式可多次写入）。
    TTL 由 expires_at 控制（默认 7 天 = PAYMENT_IDEMPOTENCY_TTL_SECONDS）。
    """

    __tablename__ = "cms_payment_idempotency"

    id = pk()
    payment_provider = Column(String(20), nullable=False)  # mock|wechat|alipay
    payment_id = Column(String(128), nullable=True)  # 网关交易号；mock 为 NULL
    order_id = Column(BigInteger, ForeignKey("cms_product_order.id"), nullable=False)
    request_body_hash = Column(String(64), nullable=False)  # SHA-256 hex
    response_body = Column(Text, nullable=True)
    response_status_code = Column(Integer, nullable=True)
    response_content_type = Column(String(100), nullable=True)
    result_status = Column(String(20), nullable=True)  # processing|succeeded|failed
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=False)

    __table_args__ = (
        # 部分唯一索引：仅 payment_id 非空时强制唯一（PG + SQLite 双支持）
        Index(
            "uq_cms_payment_idempotency",
            "payment_provider",
            "payment_id",
            unique=True,
            postgresql_where=text("payment_id IS NOT NULL"),
            sqlite_where=text("payment_id IS NOT NULL"),
        ),
        Index("idx_cms_payment_idempotency_expires", "expires_at"),
        Index("idx_cms_payment_idempotency_order", "order_id"),
    )


class WebhookRetry(Base):
    """webhook 发卡任务持久化重试（P0 Day 1.1，表 cms_webhook_retry）

    一单最多一个发卡任务（order_id UNIQUE）。status: pending|running|retry|succeeded|failed。
    poller 按 (status, next_retry_at) 扫描到期任务，PG 用 FOR UPDATE SKIP LOCKED 抢占。
    """

    __tablename__ = "cms_webhook_retry"

    id = pk()
    order_id = Column(BigInteger, ForeignKey("cms_product_order.id"), nullable=False)
    payload = Column(JSON, default=dict)  # webhook 原始 payload（重试复跑用）
    attempts = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime, nullable=False)
    last_error = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending|running|retry|succeeded|failed
    locked_at = Column(DateTime, nullable=True)  # 预留 lease（当前用 FOR UPDATE SKIP LOCKED 抢占，此列暂未启用）
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_cms_webhook_retry_order"),
        Index("idx_cms_webhook_retry_status", "status", "next_retry_at"),
    )


class OrderCard(Base):
    """订单-卡关联（P0 Day 1.1，表 cms_order_card，一单多卡）

    每张发出的 AssetCard 记一行；uq (order_id, card_id) 防重复发卡。
    卡密码不落此表（仍在 AssetCard.password_hash）；多卡密码由发卡时一次性返回。
    """

    __tablename__ = "cms_order_card"

    id = pk()
    order_id = Column(BigInteger, ForeignKey("cms_product_order.id"), nullable=False)
    card_id = Column(BigInteger, ForeignKey("asset_card.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("order_id", "card_id", name="uq_cms_order_card"),
        Index("idx_cms_order_card_order", "order_id"),
    )


class PaymentExceptionEvent(Base):
    """支付异常事件记录（P0 Day 2.1 缺口 #4，表 cms_payment_exception_event）

    三类持久化需求：
    1. 微信支付确认冲突（金额不符/状态非法/订单不存在）
    2. webhook 重试耗尽（attempts 达 MAX_RETRY_ATTEMPTS）
    3. webhook 解析失败（验签不过/JSON 解析失败）

    字段说明：
    - event_type: 事件类型（payment_conflict / webhook_retry_exhausted /
      parse_failed / order_sync_failed / other）
    - severity: info | warning | critical（critical 必触发告警）
    - detail: JSON 详情（结构化），包含 last_error/attempts/raw_payload 摘要
    - payment_id: 微信支付 transaction_id（可空）
    - order_id: 关联订单（可空，比如订单不存在时）

    索引：event_type / order_id / payment_id / created_at 便于按维度查询告警历史。
    """

    __tablename__ = "cms_payment_exception_event"

    id = pk()
    event_type = Column(String(50), nullable=False, index=True)
    order_id = Column(BigInteger, ForeignKey("cms_product_order.id"), nullable=True, index=True)
    payment_id = Column(String(100), nullable=True, index=True)
    severity = Column(String(20), nullable=False, default="warning")  # info|warning|critical
    detail = Column(Text, nullable=True)  # JSON 字符串（结构化详情）
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    __table_args__ = (
        Index("idx_cms_payment_exception_event_type_time", "event_type", "created_at"),
    )
