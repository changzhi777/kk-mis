"""MLX Whisper ASR 服务 - FastAPI 入口"""
import logging
import re
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from .config import settings
from .schemas import ErrorResponse, HealthResponse, TranscriptionResult
from .transcriber import get_transcriber

# 日志配置
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mlx-asr")

def _safe_filename(filename: str) -> str:
    """Sanitize filename: 只保留 ASCII 字母数字 + ._-"""
    if not filename:
        return "audio"
    name = Path(filename).name  # 去除路径部分
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    if len(safe) > 100:
        stem = Path(safe).stem[:80]
        suffix = Path(safe).suffix
        safe = stem + suffix
    return safe or "audio"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期（替代 deprecated @app.on_event）"""
    logger.info("=" * 60)
    logger.info("MLX Whisper ASR 服务启动中...")
    logger.info(f"  - 模型: {settings.model_name}")
    logger.info(f"  - 缓存目录: {settings.cache_dir}")
    logger.info(f"  - 监听: {settings.host}:{settings.port}")
    logger.info(f"  - 默认语言: {settings.default_language}")
    logger.info(f"  - 最大上传: {settings.max_upload_size_mb} MB")
    logger.info("=" * 60)

    # 启动后台任务预热模型
    import asyncio

    async def _warmup():
        try:
            transcriber = get_transcriber()
            transcriber.warmup()
            logger.info("✅ 模型预热完成")
        except Exception as e:
            logger.error(f"❌ 模型预热失败: {e}")

    asyncio.create_task(_warmup())
    yield
    logger.info("MLX Whisper ASR 服务关闭")


app = FastAPI(
    title="MLX Whisper ASR",
    description="本地 Mac MLX Whisper 语音转文字服务（Apple Silicon 优化）",
    version="1.0.0",
    lifespan=lifespan,
)


def _check_api_key(x_api_key: str = Header(None)):
    """校验 API Key"""
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


@app.get("/health", response_model=HealthResponse)
async def health():
    """健康检查（无需鉴权）"""
    transcriber = get_transcriber()
    return HealthResponse(
        status="ok",
        model=settings.model_name,
        cache_dir=settings.cache_dir,
    )


@app.get("/models")
async def models(_: str = Header(None, alias="X-API-Key")):
    """列出模型（需鉴权）"""
    _check_api_key(_)
    transcriber = get_transcriber()
    return {
        "current": transcriber._model_name,
        "loaded": transcriber._loaded,
    }


@app.post(
    "/transcribe",
    response_model=TranscriptionResult,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def transcribe(
    audio: UploadFile = File(..., description="音频文件（mp3/wav/m4a/flac 等）"),
    language: str = Form(default=None, description="语言代码（zh/en/ja 等，None=自动检测）"),
    beam_size: int = Form(default=None, description="beam search 宽度，默认 5"),
    x_api_key: str = Header(None, alias="X-API-Key"),
):
    """转写音频文件

    Args:
        audio: 音频文件
        language: 语言代码（默认自动检测）
        beam_size: beam search 宽度

    Returns:
        TranscriptionResult: 转写结果
    """
    _check_api_key(x_api_key)

    # 文件大小检查
    file_size_mb = audio.size / 1024 / 1024 if audio.size else 0
    if file_size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f}MB > {settings.max_upload_size_mb}MB",
        )

    # 保存到临时文件（用 sanitize 后的文件名防路径遍历）
    safe_name = _safe_filename(audio.filename or "audio")
    suffix = Path(safe_name).suffix or ".tmp"
    tmp_dir = Path(tempfile.gettempdir()) / "mlx-asr"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # 用 UUID 避免冲突
    import uuid

    tmp_file = tmp_dir / f"upload_{uuid.uuid4().hex}_{safe_name}"
    try:
        with tmp_file.open("wb") as f:
            shutil.copyfileobj(audio.file, f)

        logger.info(
            f"Received: {audio.filename} ({file_size_mb:.2f}MB), lang={language}, beam={beam_size}"
        )

        # 转写
        transcriber = get_transcriber()
        result = transcriber.transcribe(
            tmp_file,
            language=language,
            beam_size=beam_size,
        )

        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Transcribe failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcribe failed: {str(e)}")
    finally:
        # 清理临时文件
        if tmp_file.exists():
            tmp_file.unlink()


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )