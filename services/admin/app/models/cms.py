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
    Integer,
    Numeric,
    String,
    Text,
)

from ..utils import utcnow
from .base import Base
from .enterprise import pk


class MediaAsset(Base):
    """素材库（图片/视频）"""

    __tablename__ = "cms_media_asset"

    id = pk()
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False)  # image|video
    url = Column(String(500), nullable=False)
    size = Column(Integer, default=0)  # 字节
    alt = Column(String(200), nullable=True)  # 图片说明
    tags = Column(JSON, default=list)  # 标签列表
    uploaded_by = Column(BigInteger, nullable=True)
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
    pay_status = Column(String(20), default="pending", nullable=False, index=True)  # pending|paid|cancelled
    paid_at = Column(DateTime, nullable=True)
    issued_card_no = Column(String(32), nullable=True)  # 支付后发的卡号（明文一次性给买家）
    issued_card_password = Column(String(10), nullable=True)  # 卡密码（明文一次性）
    transaction_id = Column(String(100), nullable=True)  # 支付网关交易号
    created_at = Column(DateTime, default=utcnow)


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
