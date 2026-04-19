"""
AI 生成レポート API
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user_required
from ..database import get_db
from ..models import GeneratedReport, Member

router = APIRouter(prefix="/reports", tags=["reports"])


class GeneratedReportResponse(BaseModel):
    id: int
    report_type: str
    period_start: date
    period_end: date
    markdown_content: Optional[str] = None
    google_doc_url: Optional[str] = None
    google_pdf_url: Optional[str] = None
    total_reports: Optional[int] = None
    model_used: Optional[str] = None
    generated_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("", response_model=List[GeneratedReportResponse])
def list_reports(
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    q = db.query(GeneratedReport)
    if current_user.role == "employee":
        q = q.filter(GeneratedReport.report_type == "general")
    reports = q.order_by(GeneratedReport.generated_at.desc()).limit(100).all()
    return [
        GeneratedReportResponse(
            id=r.id,
            report_type=r.report_type,
            period_start=r.period_start,
            period_end=r.period_end,
            markdown_content=r.markdown_content,
            google_doc_url=r.google_doc_url,
            google_pdf_url=r.google_pdf_url,
            total_reports=r.total_reports,
            model_used=r.model_used,
            generated_at=r.generated_at.isoformat() if r.generated_at else None,
        )
        for r in reports
    ]


@router.get("/{report_id}", response_model=GeneratedReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    report = db.query(GeneratedReport).filter(GeneratedReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="レポートが見つかりません")
    if report.report_type == "executive" and current_user.role == "employee":
        raise HTTPException(status_code=403, detail="閲覧権限がありません")
    return GeneratedReportResponse(
        id=report.id,
        report_type=report.report_type,
        period_start=report.period_start,
        period_end=report.period_end,
        markdown_content=report.markdown_content,
        google_doc_url=report.google_doc_url,
        google_pdf_url=report.google_pdf_url,
        total_reports=report.total_reports,
        model_used=report.model_used,
        generated_at=report.generated_at.isoformat() if report.generated_at else None,
    )
