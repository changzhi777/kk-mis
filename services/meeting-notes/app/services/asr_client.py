"""ASR 集群客户端封装 - 适配 meeting-notes 主应用
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class ASRClusterClient:
    """ASR 集群客户端（直接调用 MLX 节点）"""

    def __init__(self):
        self.node_url = settings.default_asr_node_url
        self.api_key = settings.mlx_asr_api_key
        self.timeout = 1800.0  # 30 分钟

    async def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
    ) -> dict:
        """直接调用 MLX ASR 节点转写"""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            f"Transcribing {audio_path.name} via {self.node_url} "
            f"({audio_path.stat().st_size / 1024 / 1024:.1f}MB)"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with audio_path.open("rb") as f:
                files = {"audio": (audio_path.name, f, "application/octet-stream")}
                data = {}
                if language:
                    data["language"] = language
                headers = {"X-API-Key": self.api_key}

                resp = await client.post(
                    f"{self.node_url}/transcribe",
                    files=files,
                    data=data,
                    headers=headers,
                )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"ASR node returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )
                result = resp.json()
                result["_node_id"] = "mlx-mac-m5"
                logger.info(
                    f"Transcribed {audio_path.name}: "
                    f"{len(result.get('text', ''))} chars"
                )
                return result