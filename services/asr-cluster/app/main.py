"""ASR 集群管理 API"""
import asyncio
import logging
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .client import get_client
from .nodes import ASRNode, get_monitor, get_registry

logging.basicConfig(
    level="INFO", format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("asr-cluster")

app = FastAPI(
    title="ASR Cluster Manager",
    description="多 MLX 节点 ASR 集群管理",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event():
    """启动时初始化监控"""
    monitor = get_monitor()
    await monitor.start()
    logger.info("ASR Cluster Manager started")


@app.on_event("shutdown")
async def shutdown_event():
    monitor = get_monitor()
    await monitor.stop()


class RegisterNodeRequest(BaseModel):
    """注册节点请求"""

    id: str
    url: str
    api_key: str
    model: str = ""
    priority: int = 0
    max_concurrent: int = 2


class RegisterNodeResponse(BaseModel):
    """注册响应"""

    success: bool
    message: str
    node: dict


@app.get("/")
async def root():
    return {
        "service": "asr-cluster",
        "version": "1.0.0",
        "nodes_count": len(get_registry().list_all()),
    }


@app.get("/nodes")
async def list_nodes() -> List[dict]:
    """列出所有节点"""
    return get_client().list_nodes()


@app.post("/nodes/register", response_model=RegisterNodeResponse)
async def register_node(req: RegisterNodeRequest):
    """注册新节点"""
    registry = get_registry()
    if registry.get(req.id):
        raise HTTPException(400, f"Node {req.id} already exists")
    node = ASRNode(
        id=req.id,
        url=req.url,
        api_key=req.api_key,
        model=req.model,
        priority=req.priority,
        max_concurrent=req.max_concurrent,
    )
    registry.register(node)
    return RegisterNodeResponse(
        success=True,
        message=f"Node {req.id} registered",
        node=node.to_dict(),
    )


@app.delete("/nodes/{node_id}")
async def deregister_node(node_id: str):
    """注销节点"""
    registry = get_registry()
    if not registry.get(node_id):
        raise HTTPException(404, f"Node {node_id} not found")
    registry.deregister(node_id)
    return {"success": True, "message": f"Node {node_id} deregistered"}


@app.post("/transcribe")
async def transcribe_dispatch(audio_path: str, language: str = None):
    """通过集群转写（自动负载均衡）"""
    from pathlib import Path

    if not Path(audio_path).exists():
        raise HTTPException(404, f"Audio file not found: {audio_path}")
    try:
        client = get_client()
        result = await client.transcribe(audio_path, language=language)
        return result
    except RuntimeError as e:
        raise HTTPException(503, str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=9100, log_level="info")