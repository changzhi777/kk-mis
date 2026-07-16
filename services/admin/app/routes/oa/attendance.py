"""考勤：上下班打卡 + 我的记录 + 当月统计（独立，不走审批）

规则（本地时间）：上班 09:00 / 下班 18:00
- 09:00 后打卡 → late（迟到）
- 18:00 前下班 → early（早退）
"""
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import get_session
from ...deps import get_current_user
from ...models import Attendance, User
from ...schemas.oa import AttendanceOut
from ...utils import to_csv

router = APIRouter(prefix="/api/v1/oa/attendance", tags=["oa-attendance"])

# 考勤规则（KISS：常量硬编码，后续可抽到配置）
WORK_START_HOUR = 9
WORK_END_HOUR = 18

# 考勤按东八区（Asia/Shanghai）本地时间判定，避免服务器时区漂移导致打卡状态错（MEDIUM）
_CST = timezone(timedelta(hours=8))


def _now_cst() -> datetime:
    """当前东八区时间（naive，适配 Attendance DateTime 列；按本地时间判迟到/早退）。"""
    return datetime.now(_CST).replace(tzinfo=None)


def _today_cst() -> date:
    """当前东八区日期（打卡按本地日归属）。"""
    return _now_cst().date()


@router.post("/clock-in", response_model=AttendanceOut)
async def clock_in(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """上班打卡（每日仅一次）"""
    today = _today_cst()
    att = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id == user.id, Attendance.date == today
            )
        )
    ).scalar_one_or_none()
    if att and att.clock_in:
        raise HTTPException(400, "今日已上班打卡")
    now = _now_cst()
    is_late = now.hour > WORK_START_HOUR or (
        now.hour == WORK_START_HOUR and now.minute > 0
    )
    status = "late" if is_late else "normal"
    if not att:
        att = Attendance(user_id=user.id, date=today, clock_in=now, status=status)
        session.add(att)
    else:
        att.clock_in = now
        att.status = status
    await session.commit()
    await session.refresh(att)
    return AttendanceOut.model_validate(att)


@router.post("/clock-out", response_model=AttendanceOut)
async def clock_out(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """下班打卡（须先上班打卡，计算工时）"""
    today = _today_cst()
    att = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id == user.id, Attendance.date == today
            )
        )
    ).scalar_one_or_none()
    if not att or not att.clock_in:
        raise HTTPException(400, "请先上班打卡")
    if att.clock_out:
        raise HTTPException(400, "今日已下班打卡")
    now = _now_cst()
    att.clock_out = now
    # 早退覆盖状态（迟到不因准点下班而清除）
    if now.hour < WORK_END_HOUR:
        att.status = "early"
    att.work_hours = Decimal(str(round((now - att.clock_in).total_seconds() / 3600, 1)))
    await session.commit()
    await session.refresh(att)
    return AttendanceOut.model_validate(att)


@router.get("/today")
async def today_record(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """今日打卡状态（前端打卡卡片用）"""
    today = _today_cst()
    att = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id == user.id, Attendance.date == today
            )
        )
    ).scalar_one_or_none()
    if not att:
        return {"clock_in": None, "clock_out": None, "status": None}
    return AttendanceOut.model_validate(att).model_dump()


@router.get("/me")
async def my_attendance(
    month: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """我的月度打卡明细（month=YYYY-MM，默认当月）"""
    y, m = _parse_month(month)
    rs = (
        await session.execute(
            select(Attendance)
            .where(
                Attendance.user_id == user.id,
                extract("year", Attendance.date) == y,
                extract("month", Attendance.date) == m,
            )
            .order_by(Attendance.date.desc())
        )
    ).scalars().all()
    return {"items": [AttendanceOut.model_validate(a).model_dump() for a in rs]}


@router.get("/stats")
async def my_stats(
    month: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """我的月度统计：出勤/迟到/早退天数 + 总工时"""
    y, m = _parse_month(month)
    rs = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id == user.id,
                extract("year", Attendance.date) == y,
                extract("month", Attendance.date) == m,
            )
        )
    ).scalars().all()
    normal = sum(1 for a in rs if a.status == "normal")
    late = sum(1 for a in rs if a.status == "late")
    early = sum(1 for a in rs if a.status == "early")
    hours = sum((a.work_hours or 0) for a in rs)
    return {
        "month": f"{y:04d}-{m:02d}",
        "total": len(rs),
        "normal": normal,
        "late": late,
        "early": early,
        "work_hours_sum": float(hours),
    }


@router.get("/export")
async def export_attendance(
    month: str | None = None,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """导出我的考勤为 CSV"""
    y, m = _parse_month(month)
    rs = (
        await session.execute(
            select(Attendance)
            .where(
                Attendance.user_id == user.id,
                extract("year", Attendance.date) == y,
                extract("month", Attendance.date) == m,
            )
            .order_by(Attendance.date.desc())
        )
    ).scalars().all()
    status_map = {"normal": "正常", "late": "迟到", "early": "早退"}
    rows = [{
        "date": a.date,
        "clock_in": a.clock_in,
        "clock_out": a.clock_out,
        "work_hours": a.work_hours,
        "status": status_map.get(a.status, a.status),
    } for a in rs]
    cols = [("date", "日期"), ("clock_in", "上班"), ("clock_out", "下班"),
            ("work_hours", "工时(h)"), ("status", "状态")]
    data = to_csv(rows, cols)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="attendance_{y:04d}-{m:02d}.csv"'},
    )


def _parse_month(month: str | None) -> tuple[int, int]:
    """解析 YYYY-MM，默认当月"""
    if month:
        try:
            y, m = map(int, month.split("-"))
            return y, m
        except Exception:
            pass
    t = _today_cst()
    return t.year, t.month
