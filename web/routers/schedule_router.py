"""
レポートスケジュール管理 API（admin 専用）。
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Member, ReportSchedule
from ..services.scheduler_service import (
    parse_days_of_week,
    refresh_next_run_at,
    _run_one,
)

router = APIRouter(prefix="/admin/schedules", tags=["admin-schedules"])


# --- Pydantic スキーマ ---


_VALID_REPORT_TYPES = {"general", "executive", "both"}


class ScheduleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    report_type: str = "both"
    days_of_week: List[int] = Field(default_factory=list)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    timezone: str = "Asia/Tokyo"
    enabled: bool = True

    @field_validator("report_type")
    @classmethod
    def _check_report_type(cls, v: str) -> str:
        if v not in _VALID_REPORT_TYPES:
            raise ValueError(f"report_type must be one of {sorted(_VALID_REPORT_TYPES)}")
        return v

    @field_validator("days_of_week")
    @classmethod
    def _check_days(cls, v: List[int]) -> List[int]:
        for d in v:
            if not 0 <= d <= 6:
                raise ValueError("days_of_week values must be 0..6 (Mon=0)")
        return sorted(set(v))


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    report_type: Optional[str] = None
    days_of_week: Optional[List[int]] = None
    hour: Optional[int] = Field(default=None, ge=0, le=23)
    minute: Optional[int] = Field(default=None, ge=0, le=59)
    timezone: Optional[str] = None
    enabled: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    name: str
    report_type: str
    days_of_week: List[int]
    hour: int
    minute: int
    timezone: str
    enabled: bool
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, m: ReportSchedule) -> "ScheduleResponse":
        return cls(
            id=m.id,
            name=m.name,
            report_type=m.report_type or "both",
            days_of_week=parse_days_of_week(m.days_of_week or ""),
            hour=int(m.hour),
            minute=int(m.minute),
            timezone=m.timezone or "Asia/Tokyo",
            enabled=bool(m.enabled),
            next_run_at=m.next_run_at,
            last_run_at=m.last_run_at,
            last_run_status=m.last_run_status,
            created_by_id=m.created_by_id,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )


# --- ヘルパ ---


def _days_to_csv(days: List[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days)))


# --- API エンドポイント ---


@router.get("", response_model=List[ScheduleResponse])
def list_schedules(
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_admin),
):
    rows = db.query(ReportSchedule).order_by(ReportSchedule.id).all()
    return [ScheduleResponse.from_model(r) for r in rows]


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_admin),
):
    if not payload.days_of_week:
        raise HTTPException(status_code=400, detail="days_of_week は最低1つ選択してください")
    s = ReportSchedule(
        name=payload.name,
        report_type=payload.report_type,
        days_of_week=_days_to_csv(payload.days_of_week),
        hour=payload.hour,
        minute=payload.minute,
        timezone=payload.timezone,
        enabled=payload.enabled,
        created_by_id=current_user.id if current_user.id else None,
    )
    refresh_next_run_at(s)
    db.add(s)
    db.commit()
    db.refresh(s)
    return ScheduleResponse.from_model(s)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_admin),
):
    s = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="schedule not found")

    data = payload.model_dump(exclude_unset=True)
    if "days_of_week" in data:
        if not data["days_of_week"]:
            raise HTTPException(status_code=400, detail="days_of_week は最低1つ選択してください")
        s.days_of_week = _days_to_csv(data.pop("days_of_week"))
    for k, v in data.items():
        setattr(s, k, v)

    refresh_next_run_at(s)
    db.commit()
    db.refresh(s)
    return ScheduleResponse.from_model(s)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_admin),
):
    s = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="schedule not found")
    db.delete(s)
    db.commit()
    return None


@router.post("/{schedule_id}/run-now")
def run_now(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_admin),
):
    """admin が UI から手動でスケジュールを発火させる。同期実行。"""
    s = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="schedule not found")
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    outcome = _run_one(db, s, now_utc_naive)
    db.commit()
    return outcome
