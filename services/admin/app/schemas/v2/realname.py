"""V2.0 实名 schema（M2.6：三要素 API，注册即实名）"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class V2RealnameVerify(BaseModel):
    """提交实名（三要素：姓名 + 身份证号；id_card 不落明文，仅存 SHA256 hash）。"""

    real_name: str = Field(..., min_length=2, max_length=50)
    id_card_no: str = Field(..., min_length=15, max_length=18)


class V2RealnameStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    realname_status: str  # unverified / verified
    real_name: Optional[str] = None
    id_card_masked: Optional[str] = None  # 脱敏展示（如 110***********1234）
