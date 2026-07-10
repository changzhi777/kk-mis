"""MLX Whisper 转写核心"""
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from .config import settings
from .schemas import Segment, TranscriptionResult

logger = logging.getLogger(__name__)


# ===== Lazy Monkey-patch 兼容新版 transformers config.json =====
# 新版 transformers 生成的 Whisper config.json 含 50+ 字段，
# 而 mlx_whisper 的 ModelDimensions dataclass 只接受 10 个字段。
# 用 lazy 单次 patch：只在首次 transcribe 时打补丁，避免 import 副作用。
_patch_lock = threading.Lock()
_patched = False


def _ensure_mlx_whisper_patched():
    """确保 mlx_whisper 被打补丁（幂等）"""
    global _patched
    if _patched:
        return

    with _patch_lock:
        if _patched:
            return

        import mlx_whisper
        from mlx_whisper import whisper as _mlx_module

        _original = _mlx_module.ModelDimensions.__init__

        def _patched_init(self, **kwargs):
            """接受任意 kwargs（忽略未知字段），只传 ModelDimensions 认识的字段"""
            valid_fields = {
                "n_mels", "n_audio_ctx", "n_audio_state", "n_audio_head", "n_audio_layer",
                "n_vocab", "n_text_ctx", "n_text_state", "n_text_head", "n_text_layer",
            }
            field_map = {
                "num_mel_bins": "n_mels",
                "max_source_positions": "n_audio_ctx",
                "d_model": None,
                "encoder_attention_heads": "n_audio_head",
                "num_hidden_layers": None,
                "vocab_size": "n_vocab",
                "max_target_positions": "n_text_ctx",
                "decoder_attention_heads": "n_text_head",
                "decoder_layers": "n_text_layer",
                "encoder_layers": "n_audio_layer",
            }

            mapped = {}
            for k, v in kwargs.items():
                if k in valid_fields:
                    mapped[k] = v
                elif k in field_map:
                    target = field_map[k]
                    if target is None:
                        if k == "d_model":
                            mapped["n_audio_state"] = v
                            mapped["n_text_state"] = v
                        elif k == "num_hidden_layers":
                            mapped["n_audio_layer"] = v
                            mapped["n_text_layer"] = v
                    else:
                        mapped[target] = v
                # 其他字段忽略

            _original(self, **mapped)

        _mlx_module.ModelDimensions.__init__ = _patched_init
        _patched = True
        logger.info("✅ Patched mlx_whisper.ModelDimensions for newer transformers config")


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
        # lazy patch（幂等）
        _ensure_mlx_whisper_patched()
        import mlx_whisper

        try:
            import numpy as np

            # 0.5 秒静音
            audio = np.zeros(8000, dtype=np.float32)
            mlx_whisper.transcribe(
                audio,
                path_or_hf_repo=self._model_name,
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
        # lazy patch（幂等）
        _ensure_mlx_whisper_patched()
        import mlx_whisper

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        lang = language or settings.default_language
        # mlx_whisper 暂不支持 beam search，用 greedy (temperature=0)
        beam = beam_size or settings.beam_size

        logger.info(f"Transcribing: {audio_path} (lang={lang})")
        t0 = time.time()

        result = mlx_whisper.transcribe(
            str(audio_path),
            path_or_hf_repo=self._model_name,
            language=lang,
            temperature=0,  # greedy decoding (mlx_whisper 不支持 beam)
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