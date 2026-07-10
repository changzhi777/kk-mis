"""会议纪要 API 路由"""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..models import Meeting
from ..schemas import (
    ActionItem,
    HealthResponse,
    MeetingCreate,
    MeetingListResponse,
    MeetingResponse,
    MeetingStatus,
    Segment,
    UploadResponse,
)
from ..services.asr_client import ASRClusterClient
from ..services.notes import MeetingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])


@router.post("/upload", response_model=UploadResponse)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(..., description="音频文件 (mp3/wav/m4a/flac)"),
    title: str = Form(..., description="会议标题"),
    description: Optional[str] = Form(None, description="会议描述"),
    meeting_date: Optional[str] = Form(None, description="会议日期 ISO 格式"),
    language: str = Form(default="zh", description="音频语言"),
    session: AsyncSession = Depends(get_session),
):
    """上传音频文件，自动触发 ASR + LLM 整理流程"""
    # 1. 校验文件
    file_size_mb = (audio.size or 0) / 1024 / 1024
    if file_size_mb > settings.max_upload_size_mb:
        raise HTTPException(413, f"文件太大: {file_size_mb:.1f}MB > {settings.max_upload_size_mb}MB")

    # 2. 保存到磁盘
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{audio.filename}"
    audio_path = upload_dir / safe_filename
    with audio_path.open("wb") as f:
        shutil.copyfileobj(audio.file, f)

    # 3. 创建会议记录
    meeting = Meeting(
        title=title,
        description=description,
        meeting_date=datetime.fromisoformat(meeting_date) if meeting_date else None,
        audio_filename=audio.filename,
        audio_path=str(audio_path),
        audio_size_bytes=audio.size,
        language=language,
        status=MeetingStatus.UPLOADED.value,
    )
    session.add(meeting)
    await session.commit()
    await session.refresh(meeting)

    # 4. 后台任务：处理会议（ASR + LLM）
    background_tasks.add_task(
        _process_meeting_task,
        meeting.id,
        audio_path,
        language,
    )

    return UploadResponse(
        meeting_id=meeting.id,
        filename=audio.filename,
        size_mb=file_size_mb,
        status=MeetingStatus.UPLOADED,
        message="音频已上传，ASR + LLM 整理任务已启动",
    )


async def _process_meeting_task(meeting_id: int, audio_path: Path, language: str):
    """后台任务：处理会议"""
    from ..db import SessionLocal

    async with SessionLocal() as session:
        try:
            meeting = await session.get(Meeting, meeting_id)
            if not meeting:
                logger.error(f"Meeting {meeting_id} not found")
                return
            service = MeetingService()
            updated_meeting = await service.process_meeting(meeting, audio_path, language)
            session.add(updated_meeting)
            await session.commit()
            logger.info(f"Meeting {meeting_id} processed: status={updated_meeting.status}")
        except Exception as e:
            logger.exception(f"Background task failed: {e}")
            meeting = await session.get(Meeting, meeting_id)
            if meeting:
                meeting.status = MeetingStatus.FAILED.value
                meeting.error_message = str(e)[:1000]
                await session.commit()


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: int,
    session: AsyncSession = Depends(get_session),
):
    """获取会议详情"""
    meeting = await session.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, f"Meeting {meeting_id} not found")
    return _meeting_to_response(meeting)


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    """列出会议（分页）"""
    stmt = select(Meeting).order_by(desc(Meeting.created_at))
    if status:
        stmt = stmt.where(Meeting.status == status)

    # 计算总数
    count_stmt = select(Meeting)
    if status:
        count_stmt = count_stmt.where(Meeting.status == status)
    total = len((await session.execute(count_stmt)).scalars().all())

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    meetings = (await session.execute(stmt)).scalars().all()

    return MeetingListResponse(
        total=total,
        items=[_meeting_to_response(m) for m in meetings],
        page=page,
        page_size=page_size,
    )


@router.delete("/{meeting_id}")
async def delete_meeting(
    meeting_id: int,
    session: AsyncSession = Depends(get_session),
):
    """删除会议"""
    meeting = await session.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(404, f"Meeting {meeting_id} not found")
    # 删除音频文件
    if meeting.audio_path:
        try:
            Path(meeting.audio_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to delete audio file: {e}")
    await session.delete(meeting)
    await session.commit()
    return {"success": True, "message": f"Meeting {meeting_id} deleted"}


def _meeting_to_response(meeting: Meeting) -> MeetingResponse:
    """Meeting ORM → MeetingResponse"""
    return MeetingResponse(
        id=meeting.id,
        title=meeting.title,
        description=meeting.description,
        meeting_date=meeting.meeting_date,
        duration=meeting.audio_duration,
        status=MeetingStatus(meeting.status),
        raw_transcript=meeting.raw_transcript,
        segments=[Segment(**s) for s in (meeting.segments or [])],
        summary=meeting.summary,
        key_points=meeting.key_points or [],
        decisions=meeting.decisions or [],
        action_items=[ActionItem(**a) for a in (meeting.action_items or [])],
        audio_filename=meeting.audio_filename,
        asr_model=meeting.asr_model,
        llm_model=meeting.llm_model,
        language=meeting.language,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        completed_at=meeting.completed_at,
        error_message=meeting.error_message,
    )