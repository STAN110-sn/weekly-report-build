"""
週報提出 API
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user_required
from ..database import get_db
from ..models import Member, WeeklyReport

router = APIRouter(prefix="/reports/weekly", tags=["weekly-reports"])


def _next_friday() -> date:
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    return today + timedelta(days=days_until_friday)


class WeeklyReportCreate(BaseModel):
    work_content: str
    next_week_plan: str
    requests_opinions: Optional[str] = ""


class WeeklyReportResponse(BaseModel):
    id: int
    report_date: date
    work_content: Optional[str] = None
    next_week_plan: Optional[str] = None
    requests_opinions: Optional[str] = None
    source: str
    submitted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("", response_model=WeeklyReportResponse, status_code=status.HTTP_201_CREATED)
def submit_weekly_report(
    payload: WeeklyReportCreate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    report_date = _next_friday()

    existing = (
        db.query(WeeklyReport)
        .filter(
            WeeklyReport.member_id == current_user.id,
            WeeklyReport.report_date == report_date,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="今週の週報はすでに提出済みです",
        )

    report = WeeklyReport(
        member_id=current_user.id,
        report_date=report_date,
        work_content=payload.work_content,
        next_week_plan=payload.next_week_plan,
        requests_opinions=payload.requests_opinions,
        source="web",
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return WeeklyReportResponse(
        id=report.id,
        report_date=report.report_date,
        work_content=report.work_content,
        next_week_plan=report.next_week_plan,
        requests_opinions=report.requests_opinions,
        source=report.source,
        submitted_at=report.submitted_at,
    )


@router.get("/my", response_model=List[WeeklyReportResponse])
def my_reports(
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    reports = (
        db.query(WeeklyReport)
        .filter(WeeklyReport.member_id == current_user.id)
        .order_by(WeeklyReport.report_date.desc())
        .limit(20)
        .all()
    )
    return [
        WeeklyReportResponse(
            id=r.id,
            report_date=r.report_date,
            work_content=r.work_content,
            next_week_plan=r.next_week_plan,
            requests_opinions=r.requests_opinions,
            source=r.source,
            submitted_at=r.submitted_at,
        )
        for r in reports
    ]
