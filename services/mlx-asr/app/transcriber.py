"""MLX Whisper 转写核心"""
import logging
import time
from pathlib import Path
from typing import Optional

import mlx_whisper

from .config import settings
from .schemas import Segment, TranscriptionResult

logger = logging.getLogger(__name__)


class MLXTranscriber:
    """MLX Whisper 转写器（懒加载）"""

    def __init__(self):
        self._model_name = settings.model_name
        self._cache_dir = settings.cache_dir
        self._loaded = False
        logger.info(f"MLXTranscriber init: model={self._model_name}")

    def warmup(self) -> None:
        """预热模型（首次调用触发加载）"""
        if self._loaded:
            return
        logger.info(f"Loading model: {self._model_name}")
        # mlx_whisper 懒加载，首次 transcribe 才下载
        # 这里仅做一次超短音频测试触发加载
        try:
            import numpy as np

            # 0.5 秒静音
            audio = np.zeros(8000, dtype=np.float32)
            mlx_whisper.transcribe(
                audio,
                path_or_hf_model=self._model_name,
                language=settings.default_language,
            )
            self._loaded = True
            logger.info(f"Model loaded: {self._model_name}")
        except Exception as e:
            logger.error(f"Model load failed: {e}")
            raise

    def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        beam_size: Optional[int] = None,
    ) -> TranscriptionResult:
        """转写音频文件

        Args:
            audio_path: 音频文件路径（支持 mp3/wav/m4a/flac 等，ffmpeg 解码）
            language: 语言代码（None=自动检测）
            beam_size: beam search 宽度

        Returns:
            TranscriptionResult: 转写结果
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        lang = language or settings.default_language
        beam = beam_size or settings.beam_size

        logger.info(f"Transcribing: {audio_path} (lang={lang}, beam={beam})")
        t0 = time.time()

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_model=self._model_name,
            language=lang,
            beam_size=beam,
            verbose=None,
        )

        elapsed = time.time() - t0
        logger.info(
            f"Transcribed {audio_path.name} in {elapsed:.2f}s, "
            f"text length={len(result.get('text', ''))}"
        )

        segments = [
            Segment(
                id=i,
                start=float(seg.get("start", 0)),
                end=float(seg.get("end", 0)),
                text=seg.get("text", "").strip(),
                speaker=None,  # 说话人分离需要额外步骤
            )
            for i, seg in enumerate(result.get("segments", []))
        ]

        # 计算时长
        duration = segments[-1].end if segments else 0.0

        return TranscriptionResult(
            text=result.get("text", "").strip(),
            language=result.get("language", lang),
            duration=duration,
            model=self._model_name,
            segments=segments,
        )


# 全局单例
_transcriber: Optional[MLXTranscriber] = None


def get_transcriber() -> MLXTranscriber:
    """获取转写器单例"""
    global _transcriber
    if _transcriber is None:
        _transcriber = MLXTranscriber()
    return _transcriber