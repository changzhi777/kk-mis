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
from .rebate import V2RebateRecordOut, V2RebateSettle
from .tour import (
    V2MembershipOut,
    V2ReservationCreate,
    V2ReservationOut,
    V2ResourceStockOut,
    V2TourGroupCreate,
    V2TourGroupOut,
)

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
    "V2RebateRecordOut",
    "V2RebateSettle",
    "V2TourGroupCreate",
    "V2TourGroupOut",
    "V2ResourceStockOut",
    "V2ReservationCreate",
    "V2ReservationOut",
    "V2MembershipOut",
]
