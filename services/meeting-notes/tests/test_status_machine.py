"""MeetingService 状态机测试（mock ASR + LLM）

覆盖：
- 正常流程：UPLOADED → TRANSCRIBING → TRANSCRIBED → SUMMARIZING → COMPLETED
- ASR 异常：状态置 FAILED + error_message
- LLM 异常：状态置 FAILED + error_message
- ASR 成功 + LLM 失败：状态置 FAILED（不能停在 SUMMARIZING）
"""
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.models import Meeting
from app.schemas import MeetingStatus


def _make_meeting(tmp_path: Path, audio_name: str = "test.m4a") -> Meeting:
    """造一个 UPLOADED 状态的 meeting + 真实音频文件"""
    audio = tmp_path / audio_name
    audio.write_bytes(b"fake audio data")
    m = Meeting(
        title="测试会议",
        audio_filename=audio_name,
        audio_path=str(audio),
        audio_size_bytes=audio.stat().st_size,
        language="zh",
        status=MeetingStatus.UPLOADED.value,
    )
    return m


def _run(coro):
    """Python 3.10+ 友好：asyncio.run 自动管理 loop"""
    return asyncio.run(coro)


def test_normal_flow_uploads_to_completed(tmp_path):
    """正常流程：ASR + LLM 都成功 → COMPLETED"""
    from app.services.notes import MeetingService

    svc = MeetingService(llm_provider="glm")
    meeting = _make_meeting(tmp_path)

    asr_result = {
        "text": "这是转写文本",
        "segments": [{"start": 0, "end": 5, "text": "这是转写文本"}],
        "duration": 5.0,
        "model": "whisper-large-v3",
    }
    llm_result = {
        "summary": "会议摘要",
        "key_points": ["要点1", "要点2"],
        "decisions": ["决策1"],
        "action_items": [{"task": "任务1", "owner": "张三"}],
    }

    with (
        patch.object(svc.asr_client, "transcribe", new=AsyncMock(return_value=asr_result)),
        patch(
            "app.services.notes.generate_meeting_summary",
            new=AsyncMock(return_value=llm_result),
        ),
    ):
        _run(svc.process_meeting(meeting, meeting.audio_path, language="zh"))

    assert meeting.status == MeetingStatus.COMPLETED.value
    assert meeting.raw_transcript == "这是转写文本"
    assert meeting.summary == "会议摘要"
    assert len(meeting.key_points) == 2
    assert meeting.completed_at is not None


def test_asr_failure_marks_failed_with_error_message(tmp_path):
    """ASR 抛异常 → 状态置 FAILED + 写 error_message"""
    from app.services.notes import MeetingService

    svc = MeetingService(llm_provider="glm")
    meeting = _make_meeting(tmp_path)

    with patch.object(
        svc.asr_client, "transcribe",
        new=AsyncMock(side_effect=RuntimeError("MLX node down")),
    ):
        _run(svc.process_meeting(meeting, meeting.audio_path, language="zh"))

    assert meeting.status == MeetingStatus.FAILED.value
    assert "MLX node down" in meeting.error_message
    assert meeting.completed_at is None


def test_llm_failure_marks_failed_after_asr_success(tmp_path):
    """ASR 成功 + LLM 失败 → 状态置 FAILED（不能停在 SUMMARIZING）"""
    from app.services.notes import MeetingService

    svc = MeetingService(llm_provider="glm")
    meeting = _make_meeting(tmp_path)

    asr_result = {"text": "转写成功", "segments": [], "duration": 0.0, "model": "whisper"}

    with (
        patch.object(svc.asr_client, "transcribe", new=AsyncMock(return_value=asr_result)),
        patch(
            "app.services.notes.generate_meeting_summary",
            new=AsyncMock(side_effect=TimeoutError("GLM API timeout")),
        ),
    ):
        _run(svc.process_meeting(meeting, meeting.audio_path, language="zh"))

    # ASR 成功的数据应保留
    assert meeting.raw_transcript == "转写成功"
    assert meeting.status == MeetingStatus.FAILED.value
    assert "GLM API timeout" in meeting.error_message


def test_audio_file_not_found_marks_failed(tmp_path):
    """音频文件不存在 → ASR 客户端先抛 FileNotFoundError → FAILED"""
    from app.services.notes import MeetingService

    svc = MeetingService(llm_provider="glm")
    meeting = _make_meeting(tmp_path)
    # 删除音频文件
    Path(meeting.audio_path).unlink()

    _run(svc.process_meeting(meeting, meeting.audio_path, language="zh"))

    assert meeting.status == MeetingStatus.FAILED.value
    assert "not found" in meeting.error_message.lower() or "Audio" in meeting.error_message