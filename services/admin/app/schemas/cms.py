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
    cover_image: Optional[str] = None
    summary: Optional[str] = None
    highlights: List[str] = []
    status: str
    sort: int
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
