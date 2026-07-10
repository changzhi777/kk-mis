"""会议纪要核心服务 - 协调 ASR + LLM
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Meeting
from ..schemas import MeetingStatus
from .asr_client import ASRClusterClient
from .llm import generate_meeting_summary

logger = logging.getLogger(__name__)


class MeetingService:
    """会议处理服务 - 编排 ASR + LLM 完整流程"""

    def __init__(self, llm_provider: str = "glm"):
        self.asr_client = ASRClusterClient()
        self.llm_provider = llm_provider  # glm / minimax / omlx

    async def process_meeting(
        self,
        meeting: Meeting,
        audio_path: str | Path,
        language: str = "zh",
        session: AsyncSession = None,
    ) -> Meeting:
        """处理会议：ASR → LLM 整理 → 落库

        Args:
            meeting: Meeting 数据库对象
            audio_path: 音频文件路径
            language: 语言代码
            session: 数据库 session（用于持久化）

        Returns:
            更新后的 Meeting 对象
        """
        audio_path = Path(audio_path)
        logger.info(f"Processing meeting {meeting.id}: {audio_path.name}")

        try:
            # 步骤 1: ASR 转写
            meeting.status = MeetingStatus.TRANSCRIBING.value
            if session:
                await session.commit()

            t0 = time.time()
            asr_result = await self.asr_client.transcribe(
                audio_path, language=language
            )
            asr_elapsed = time.time() - t0

            meeting.raw_transcript = asr_result.get("text", "")
            meeting.segments = asr_result.get("segments", [])
            meeting.audio_duration = asr_result.get("duration", 0.0)
            meeting.asr_model = asr_result.get("model", "")
            meeting.asr_node_id = asr_result.get("_node_id", "")
            meeting.status = MeetingStatus.TRANSCRIBED.value
            if session:
                await session.commit()

            logger.info(
                f"Meeting {meeting.id} ASR done in {asr_elapsed:.1f}s, "
                f"{len(meeting.raw_transcript or '')} chars"
            )

            # 步骤 2: LLM 整理
            meeting.status = MeetingStatus.SUMMARIZING.value
            if session:
                await session.commit()

            t0 = time.time()
            summary = await generate_meeting_summary(
                transcript=meeting.raw_transcript,
                provider=self.llm_provider,
            )
            llm_elapsed = time.time() - t0

            meeting.summary = summary.get("summary", "")
            meeting.key_points = summary.get("key_points", [])
            meeting.decisions = summary.get("decisions", [])
            meeting.action_items = summary.get("action_items", [])
            meeting.llm_model = settings.glm_model
            meeting.completed_at = datetime.utcnow()
            meeting.status = MeetingStatus.COMPLETED.value

            logger.info(
                f"Meeting {meeting.id} LLM done in {llm_elapsed:.1f}s"
            )

        except Exception as e:
            logger.exception(f"Meeting {meeting.id} processing failed: {e}")
            meeting.status = MeetingStatus.FAILED.value
            meeting.error_message = str(e)[:1000]

        # 最后一次 commit
        if session:
            await session.commit()

        return meeting


# 全局实例
_service: Optional[MeetingService] = None


def get_meeting_service() -> MeetingService:
    global _service
    if _service is None:
        _service = MeetingService()
    return _service