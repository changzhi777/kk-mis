"""ASR 集群客户端 - 任务分发器
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

from .nodes import (
    ASRNode,
    LoadBalancer,
    NodeRegistry,
    get_balancer,
    get_registry,
)

logger = logging.getLogger(__name__)


class ASRClient:
    """ASR 集群客户端 - 自动负载均衡"""

    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        balancer: Optional[LoadBalancer] = None,
        timeout: float = 1800.0,
    ):
        self.registry = registry or get_registry()
        self.balancer = balancer or get_balancer()
        self.timeout = timeout

    async def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
    ) -> dict:
        """转写音频，自动负载均衡到可用节点

        Args:
            audio_path: 音频文件路径
            language: 语言代码
            beam_size: beam search 宽度

        Returns:
            转写结果 dict (含 text/language/duration/segments/model)

        Raises:
            RuntimeError: 所有节点都不可用或转写失败
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 选节点
        node = self.balancer.pick()
        if node is None:
            raise RuntimeError(
                "No ASR node available. All nodes are offline or busy."
            )

        # 标记占用
        node.current_tasks += 1
        if node.current_tasks >= node.max_concurrent:
            node.status = "busy"

        try:
            logger.info(
                f"Dispatching to node {node.id} @ {node.url} "
                f"(file={audio_path.name}, size={audio_path.stat().st_size/1024/1024:.1f}MB)"
            )
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                with audio_path.open("rb") as f:
                    files = {"audio": (audio_path.name, f, "application/octet-stream")}
                    data = {}
                    if language:
                        data["language"] = language
                    if beam_size:
                        data["beam_size"] = beam_size
                    headers = {"X-API-Key": node.api_key}

                    resp = await client.post(
                        f"{node.url}/transcribe",
                        files=files,
                        data=data,
                        headers=headers,
                    )
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Node {node.id} returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )
                result = resp.json()
                logger.info(
                    f"Node {node.id} transcribed {audio_path.name}: "
                    f"{len(result.get('text', ''))} chars"
                )
                # 在结果中标记使用的节点
                result["_node_id"] = node.id
                return result

        except Exception as e:
            node.last_error = str(e)[:200]
            node.status = "degraded"
            logger.error(f"Transcribe failed on node {node.id}: {e}")
            raise
        finally:
            # 释放节点
            self.balancer.release(node)
            node.status = "healthy"

    def list_nodes(self) -> list[dict]:
        """列出所有节点状态"""
        return [n.to_dict() for n in self.registry.list_all()]


# 全局实例
_client: Optional[ASRClient] = None


def get_client() -> ASRClient:
    global _client
    if _client is None:
        _client = ASRClient()
    return _client