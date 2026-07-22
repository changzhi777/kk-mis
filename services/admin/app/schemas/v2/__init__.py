"""V2.0 业务 schema 聚合"""
from .activation import V2ActivationCodeCreate, V2ActivationCodeOut
from .commerce import (
    V2BalanceOut,
    V2PromoCodeOut,
    V2RechargeCreate,
    V2RechargeOut,
)
from .dealer import (
    V2DealerApplicationCreate,
    V2DealerApplicationOut,
    V2DealerApplicationReject,
    V2DealerContractCreate,
    V2DealerContractOut,
    V2DealerQualificationCreate,
    V2DealerQualificationOut,
    V2DealerQualificationVerify,
)
from .realname import V2RealnameStatus, V2RealnameVerify

__all__ = [
    "V2DealerApplicationCreate",
    "V2DealerApplicationOut",
    "V2DealerApplicationReject",
    "V2DealerContractCreate",
    "V2DealerContractOut",
    "V2DealerQualificationCreate",
    "V2DealerQualificationOut",
    "V2DealerQualificationVerify",
    "V2ActivationCodeCreate",
    "V2ActivationCodeOut",
    "V2PromoCodeOut",
    "V2RechargeCreate",
    "V2RechargeOut",
    "V2BalanceOut",
    "V2RealnameVerify",
    "V2RealnameStatus",
]
