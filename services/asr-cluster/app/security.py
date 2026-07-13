"""asr-cluster 鉴权 — X-API-Key Header。

时序安全校验（secrets.compare_digest 防 timing attack）。
API Key 从 env MLX_ASR_API_KEY 读取（与 mlx-asr 节点一致）。
"""

from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Header, HTTPException, status


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> str:
    """校验 X-API-Key（服务间调用）。缺失或错误 → 401。

    Key 从 env MLX_ASR_API_KEY 读（如未配置则拒所有调用）。
    """
    import os

    expected = os.getenv("MLX_ASR_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MLX_ASR_API_KEY 未配置（server-side）",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key