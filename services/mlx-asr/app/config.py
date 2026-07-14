"""MLX Whisper ASR 服务 - 配置"""
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    """服务配置"""

    # 服务
    host: str = "0.0.0.0"
    port: int = 9000
    debug: bool = False

    # API Key（从环境变量读）
    api_key: str = os.getenv("MLX_ASR_API_KEY", "kk-cms-asr-default-key-change-me")

    # 模型
    model_name: str = os.getenv(
        "MLX_ASR_MODEL", "mlx-community/whisper-large-v3-turbo"
    )
    cache_dir: str = os.getenv(
        "MLX_ASR_CACHE_DIR",
        str(Path(__file__).parent.parent / "models"),
    )

    # 推理参数
    default_language: str = os.getenv("MLX_ASR_DEFAULT_LANG", "zh")
    beam_size: int = int(os.getenv("MLX_ASR_BEAM_SIZE", "5"))
    max_audio_duration: int = int(os.getenv("MLX_ASR_MAX_DURATION", "7200"))  # 2h

    # 文件
    max_upload_size_mb: int = int(os.getenv("MLX_ASR_MAX_UPLOAD_MB", "500"))

    # 日志
    log_level: str = os.getenv("MLX_ASR_LOG_LEVEL", "INFO")


settings = Settings()