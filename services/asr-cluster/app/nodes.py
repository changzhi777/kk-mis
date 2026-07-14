"""ASR 集群节点管理 - 多 MLX 节点支持
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """节点状态"""

    HEALTHY = "healthy"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class ASRNode:
    """ASR 节点

    Attributes:
        id: 节点唯一标识
        url: 节点 base URL (http://host:port)
        api_key: 节点 API Key
        model: 节点加载的模型名
        priority: 调度优先级 (0=最高, 越大越低)
        max_concurrent: 最大并发任务数
    """

    id: str
    url: str
    api_key: str
    model: str = ""
    priority: int = 0
    max_concurrent: int = 2
    status: NodeStatus = NodeStatus.OFFLINE
    current_tasks: int = 0
    total_processed: int = 0
    last_heartbeat: float = 0.0
    last_error: Optional[str] = None

    @property
    def is_available(self) -> bool:
        """是否可分配任务"""
        return (
            self.status == NodeStatus.HEALTHY
            and self.current_tasks < self.max_concurrent
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "model": self.model,
            "status": self.status.value,
            "current_tasks": self.current_tasks,
            "max_concurrent": self.max_concurrent,
            "total_processed": self.total_processed,
            "priority": self.priority,
            "last_heartbeat": self.last_heartbeat,
            "is_available": self.is_available,
            "last_error": self.last_error,
        }


class NodeRegistry:
    """节点注册表"""

    def __init__(self):
        self._nodes: Dict[str, ASRNode] = {}

    def register(self, node: ASRNode) -> None:
        """注册节点"""
        self._nodes[node.id] = node
        logger.info(f"Node registered: {node.id} @ {node.url}")

    def deregister(self, node_id: str) -> None:
        """注销节点"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            logger.info(f"Node deregistered: {node_id}")

    def get(self, node_id: str) -> Optional[ASRNode]:
        return self._nodes.get(node_id)

    def list_all(self) -> List[ASRNode]:
        return list(self._nodes.values())

    def list_available(self) -> List[ASRNode]:
        """列出可用节点"""
        return [n for n in self._nodes.values() if n.is_available]


class HeartbeatMonitor:
    """心跳监控"""

    def __init__(
        self,
        registry: NodeRegistry,
        interval: float = 10.0,
        timeout: float = 30.0,
    ):
        self.registry = registry
        self.interval = interval
        self.timeout = timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """启动心跳监控"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"HeartbeatMonitor started (interval={self.interval}s)")

    async def stop(self):
        """停止心跳监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HeartbeatMonitor stopped")

    async def _loop(self):
        """心跳循环"""
        while self._running:
            try:
                await self._check_all()
            except Exception as e:
                logger.exception(f"Heartbeat loop error: {e}")
            await asyncio.sleep(self.interval)

    async def _check_all(self):
        """检查所有节点"""
        nodes = self.registry.list_all()
        if not nodes:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            tasks = [self._check_node(client, n) for n in nodes]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_node(self, client: httpx.AsyncClient, node: ASRNode):
        """检查单个节点"""
        try:
            resp = await client.get(
                f"{node.url}/health",
                headers={"X-API-Key": node.api_key} if node.api_key else None,
            )
            if resp.status_code == 200:
                node.last_heartbeat = time.time()
                if node.status != NodeStatus.BUSY:
                    node.status = NodeStatus.HEALTHY
                node.last_error = None
            else:
                node.status = NodeStatus.DEGRADED
                node.last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            node.status = NodeStatus.OFFLINE
            node.last_error = str(e)[:200]
            logger.warning(f"Node {node.id} offline: {e}")


class LoadBalancer:
    """负载均衡器 - 简单策略：最少任务 + 优先级"""

    def __init__(self, registry: NodeRegistry):
        self.registry = registry

    def pick(self) -> Optional[ASRNode]:
        """挑选最优节点"""
        available = self.registry.list_available()
        if not available:
            return None
        # 排序：(priority ASC, current_tasks ASC)
        available.sort(key=lambda n: (n.priority, n.current_tasks))
        return available[0]

    def release(self, node: ASRNode) -> None:
        """释放节点（任务完成）"""
        node.current_tasks = max(0, node.current_tasks - 1)
        node.total_processed += 1


# 全局实例
_registry: Optional[NodeRegistry] = None
_monitor: Optional[HeartbeatMonitor] = None
_balancer: Optional[LoadBalancer] = None


def get_registry() -> NodeRegistry:
    global _registry
    if _registry is None:
        _registry = NodeRegistry()
        # 默认注册 Mac 节点（通过 Tailscale）
        import os

        default_url = os.getenv("DEFAULT_ASR_NODE_URL", "http://100.88.88.34:9000")
        default_key = os.getenv("MLX_ASR_API_KEY", "kk-cms-asr-local-dev-key-2026")
        _registry.register(
            ASRNode(
                id="mlx-mac-m5",
                url=default_url,
                api_key=default_key,
                model="mlx-community/belle-whisper-large-v3-zh-punct-fp16",
                priority=0,
                max_concurrent=2,
                status=NodeStatus.OFFLINE,
            )
        )
    return _registry


def get_monitor() -> HeartbeatMonitor:
    global _monitor
    if _monitor is None:
        _monitor = HeartbeatMonitor(get_registry())
    return _monitor


def get_balancer() -> LoadBalancer:
    global _balancer
    if _balancer is None:
        _balancer = LoadBalancer(get_registry())
    return _balancer