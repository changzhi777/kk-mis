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
    cover_image = Column(String(500), nullable=True)  # 封面图 URL
    gallery = Column(JSON, default=list)  # 图集 URL 列表
    video_url = Column(String(500), nullable=True)
    summary = Column(String(500), nullable=True)  # 摘要
    content = Column(Text, nullable=True)  # 富文本 HTML（编辑器输出）
    highlights = Column(JSON, default=list)  # 亮点列表 ["", ""]
    status = Column(String(20), default="draft", nullable=False, index=True)  # draft|published|archived
    sort = Column(Integer, default=0)
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
