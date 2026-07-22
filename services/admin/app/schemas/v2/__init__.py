"""V2.0 业务 schema 聚合"""
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

__all__ = [
    "V2DealerApplicationCreate",
    "V2DealerApplicationOut",
    "V2DealerApplicationReject",
    "V2DealerContractCreate",
    "V2DealerContractOut",
    "V2DealerQualificationCreate",
    "V2DealerQualificationOut",
    "V2DealerQualificationVerify",
]
