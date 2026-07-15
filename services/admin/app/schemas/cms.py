"""CMS Schema：旅游产品（A/C）+ 素材 + 商户

产品采用嵌套结构：创建/更新产品时可一并提交 custom(订制游) / pass_config(权益卡) 扩展，
详情接口返回产品 + 对应扩展，前端一次提交/一次渲染。
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===== 素材库 =====
class MediaAssetOut(BaseModel):
    id: int
    name: str
    type: str  # image|video
    url: str
    size: int
    alt: Optional[str] = None
    tags: List[str] = []
    uploaded_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 合作商户 =====
class MerchantCreate(BaseModel):
    name: str = Field(..., max_length=100)
    logo: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None
    benefit_desc: Optional[str] = None
    status: bool = True
    sort: int = 0


class MerchantUpdate(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None
    address: Optional[str] = None
    contact: Optional[str] = None
    benefit_desc: Optional[str] = None
    status: Optional[bool] = None
    sort: Optional[int] = None


class MerchantOut(MerchantCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ===== 产品扩展（A 订制游 / C 权益卡）=====
class TourCustomSchema(BaseModel):
    """订制游扩展（A）"""

    itinerary: List[Any] = []
    service_flow: List[Any] = []
    price_mode: str = "inquiry"  # inquiry|tier
    price_tiers: List[Any] = []
    consultant_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


class TourPassSchema(BaseModel):
    """权益卡扩展（C，字段名 pass_config 避开 Python 关键字 pass）"""

    face_value: Decimal = Decimal("0")
    total_worth: Decimal = Decimal("0")
    valid_period: Optional[str] = None
    usage_rules: Optional[str] = None
    benefits: List[Any] = []
    merchant_ids: List[int] = []

    model_config = ConfigDict(from_attributes=True)


# ===== 旅游产品 =====
class TourProductCreate(BaseModel):
    title: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=200)
    type: str = Field(..., pattern="^(custom|pass)$")  # custom(订制游) | pass(权益卡)
    destination: Optional[str] = None
    theme: Optional[str] = None
    category: Optional[str] = None  # 分类：国内/海外/周边
    tags: List[str] = []
    card_type_id: Optional[int] = None  # 关联 asset 卡券类型（pass 支付后发卡）
    cover_image: Optional[str] = None
    gallery: List[str] = []
    video_url: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    highlights: List[str] = []
    status: str = "draft"  # draft|published|archived
    sort: int = 0
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    # 扩展（创建时一并写入；type=custom 用 custom，type=pass 用 pass_config）
    custom: Optional[TourCustomSchema] = None
    pass_config: Optional[TourPassSchema] = None


class TourProductUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    destination: Optional[str] = None
    theme: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    card_type_id: Optional[int] = None
    cover_image: Optional[str] = None
    gallery: Optional[List[str]] = None
    video_url: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    highlights: Optional[List[str]] = None
    status: Optional[str] = None
    sort: Optional[int] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    custom: Optional[TourCustomSchema] = None
    pass_config: Optional[TourPassSchema] = None


class TourProductOut(BaseModel):
    """产品基本信息（列表用）"""

    id: int
    title: str
    slug: str
    type: str
    destination: Optional[str] = None
    theme: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = []
    card_type_id: Optional[int] = None
    cover_image: Optional[str] = None
    summary: Optional[str] = None
    highlights: List[str] = []
    status: str
    sort: int
    view_count: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TourProductDetail(TourProductOut):
    """产品详情（含富文本/图集 + A/C 扩展）"""

    gallery: List[str] = []
    video_url: Optional[str] = None
    content: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    custom: Optional[TourCustomSchema] = None
    pass_config: Optional[TourPassSchema] = None


# ===== 询价线索（订制游 A，公开提交）=====
class InquiryLeadCreate(BaseModel):
    """询价线索公开提交（无需登录）"""

    product_id: Optional[int] = None
    name: str = Field(..., max_length=50)
    phone: str = Field(..., max_length=30)
    wechat: Optional[str] = Field(None, max_length=50)
    destination: Optional[str] = None
    travel_date: Optional[str] = None
    people: Optional[int] = None
    budget: Optional[str] = None
    remark: Optional[str] = None


class InquiryLeadOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    name: str
    phone: str
    wechat: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[str] = None
    people: Optional[int] = None
    budget: Optional[str] = None
    remark: Optional[str] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InquiryLeadStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(new|contacted|converted|closed)$")


# ===== 订单（权益卡 C）=====
class ProductOrderCreate(BaseModel):
    """公开下单（无需登录）"""

    product_id: int
    quantity: int = Field(1, ge=1)
    coupon_code: Optional[str] = None
    promo_code: Optional[str] = None  # A2 推广码（关联推荐代理）
    buyer_name: str = Field(..., max_length=50)
    buyer_phone: str = Field(..., max_length=30)
    remark: Optional[str] = None


class ProductOrderOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    original_total: Decimal
    discount: Decimal
    total: Decimal
    coupon_code: Optional[str] = None
    buyer_name: str
    buyer_phone: str
    remark: Optional[str] = None
    pay_status: str
    paid_at: Optional[datetime] = None
    transaction_id: Optional[str] = None
    issued_card_no: Optional[str] = None
    issued_card_password: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===== 优惠券 =====
class CouponCreate(BaseModel):
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    discount_type: str = Field(..., pattern="^(percent|fixed)$")
    discount_value: Decimal
    min_total: Decimal = Decimal("0")
    max_uses: int = 0  # 0=不限
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: bool = True


class CouponUpdate(BaseModel):
    name: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    min_total: Optional[Decimal] = None
    max_uses: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    status: Optional[bool] = None


class CouponOut(CouponCreate):
    id: int
    used_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CouponValidateRequest(BaseModel):
    code: str
    total: Decimal  # 订单原价


class CouponValidateResponse(BaseModel):
    valid: bool
    discount: Decimal = Decimal("0")
    reason: Optional[str] = None


# ===== 评论/评价 =====
class ReviewCreate(BaseModel):
    product_id: int
    author_name: str = Field(..., max_length=50)
    rating: int = Field(..., ge=1, le=5)
    content: str = Field(..., min_length=1, max_length=1000)


class ReviewOut(BaseModel):
    id: int
    product_id: int
    author_name: str
    rating: int
    content: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")


# ===== 看板统计 =====
class DashboardStats(BaseModel):
    products_total: int
    products_published: int
    views_total: int
    top_products: List[Any]
    leads_total: int
    leads_new: int
    orders_total: int
    orders_paid: int
    revenue: Decimal


# ===== C 端终端用户 =====
class EndUserRegister(BaseModel):
    phone: str = Field(..., max_length=30)
    password: str = Field(..., min_length=6, max_length=64)
    nickname: Optional[str] = Field(None, max_length=50)


class EndUserLogin(BaseModel):
    phone: str
    password: str


class EndUserOut(BaseModel):
    id: int
    phone: str
    nickname: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
