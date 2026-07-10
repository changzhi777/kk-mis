"""会议纪要 API 路由"""
import logging
import re
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
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..security import verify_jwt
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
router = APIRouter(
    prefix="/api/v1/meetings",
    tags=["meetings"],
    dependencies=[Depends(verify_jwt)],
)


def _safe_filename(filename: str) -> str:
    """Sanitize filename：只保留字母数字 + ._- ，防止路径遍历"""
    if not filename:
        return "audio"
    # 取 basename（防止 ../）
    name = Path(filename).name
    # 替换危险字符为下划线
    safe = re.sub(r'[^a-zA-Z0-9._-]', '_', name)
    # 限制长度
    if len(safe) > 100:
        stem = Path(safe).stem[:80]
        suffix = Path(safe).suffix
        safe = stem + suffix
    return safe or "audio"


@router.post("/upload", response_model=UploadResponse)
async def upload_meeting(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(..., description="音频文件 (mp3/wav/m4a/flac)"),
    title: str = Form(..., description="会议标题", min_length=1, max_length=255),
    description: Optional[str] = Form(None, description="会议描述", max_length=2000),
    meeting_date: Optional[str] = Form(None, description="会议日期 ISO 格式 (YYYY-MM-DDTHH:MM:SS)"),
    language: str = Form(default="zh", description="音频语言"),
    llm_provider: str = Form(default="glm", description="LLM 提供商: glm/minimax/omlx"),
    session: AsyncSession = Depends(get_session),
):
    """上传音频文件，自动触发 ASR + LLM 整理流程"""
    # 1. 校验文件
    file_size_mb = (audio.size or 0) / 1024 / 1024
    if file_size_mb > settings.max_upload_size_mb:
        raise HTTPException(413, f"文件太大: {file_size_mb:.1f}MB > {settings.max_upload_size_mb}MB")

    # 1.1 校验 LLM provider
    valid_providers = {"glm", "minimax", "omlx"}
    if llm_provider not in valid_providers:
        raise HTTPException(400, f"Invalid llm_provider: {llm_provider}. Must be one of {valid_providers}")

    # 1.2 校验会议日期
    parsed_meeting_date = None
    if meeting_date:
        try:
            parsed_meeting_date = datetime.fromisoformat(meeting_date)
        except ValueError:
            raise HTTPException(400, f"Invalid meeting_date format. Expected ISO format, got: {meeting_date}")

    # 1.3 Sanitize 文件名
    safe_name = _safe_filename(audio.filename or "audio")

    # 2. 保存到磁盘
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"
    audio_path = upload_dir / stored_filename
    with audio_path.open("wb") as f:
        shutil.copyfileobj(audio.file, f)

    # 3. 创建会议记录
    meeting = Meeting(
        title=title,
        description=description,
        meeting_date=parsed_meeting_date,
        audio_filename=audio.filename,  # 保留原文件名用于显示
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
        llm_provider,
    )

    return UploadResponse(
        meeting_id=meeting.id,
        filename=audio.filename,
        size_mb=file_size_mb,
        status=MeetingStatus.UPLOADED,
        message=f"音频已上传，ASR + {llm_provider.upper()} LLM 整理任务已启动",
    )


async def _process_meeting_task(
    meeting_id: int,
    audio_path: Path,
    language: str,
    llm_provider: str = "glm",
):
    """后台任务：处理会议"""
    from ..db import SessionLocal

    async with SessionLocal() as session:
        try:
            meeting = await session.get(Meeting, meeting_id)
            if not meeting:
                logger.error(f"Meeting {meeting_id} not found")
                return
            service = MeetingService(llm_provider=llm_provider)
            updated_meeting = await service.process_meeting(
                meeting, audio_path, language, session=session
            )
            logger.info(
                f"Meeting {meeting_id} processed: "
                f"status={updated_meeting.status}, llm={llm_provider}"
            )
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
    # 基础查询
    base_stmt = select(Meeting)
    if status:
        base_stmt = base_stmt.where(Meeting.status == status)

    # 计算总数（SQL COUNT，不加载数据）
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # 分页查询
    stmt = base_stmt.order_by(desc(Meeting.created_at))
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