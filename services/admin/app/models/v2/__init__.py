"""V2.0 业务模型聚合（B2B 经销商预付激活模型，2026-07-21）

物理隔离：v2/ 子目录 + v2_ 表前缀 + /admin/api/v2 路由前缀，与 kk-mis 业务隔离。
详见 memory `project-v2-app-b2b-dealer-redesign-2026-07-21`
  + .zcf/plan/current/v2-app-redesign.md
"""
from .activation import V2ActivationCode
from .dealer import (
    V2DealerApplication,
    V2DealerBalance,
    V2DealerContract,
    V2DealerQualification,
    V2DealerRecharge,
)

__all__ = [
    "V2DealerApplication",
    "V2DealerContract",
    "V2DealerBalance",
    "V2DealerRecharge",
    "V2DealerQualification",
    "V2ActivationCode",
]
