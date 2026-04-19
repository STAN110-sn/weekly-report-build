"""
DB ベース週報取得サービス（SpreadsheetService の drop-in 代替）
"""
from datetime import date
from typing import Dict, List

from sqlalchemy.orm import Session

from .models import Member, WeeklyReport


class DBReportService:
    def __init__(self, db: Session):
        self.db = db

    def get_reports_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """
        週報を日付範囲で取得し、SpreadsheetService 互換の dict リストを返す。
        """
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        rows = (
            self.db.query(WeeklyReport, Member)
            .outerjoin(Member, WeeklyReport.member_id == Member.id)
            .filter(WeeklyReport.report_date >= start, WeeklyReport.report_date <= end)
            .order_by(WeeklyReport.report_date)
            .all()
        )

        result = []
        for report, member in rows:
            name = ""
            department = "Other"
            if member:
                name = member.name
                department = member.department or "Other"
            elif report.submitter_name:
                name = report.submitter_name

            submitted_at = report.submitted_at or report.report_date
            requests = report.requests_opinions or report.company_feedback or ""

            result.append({
                "タイムスタンプ": submitted_at.isoformat() if hasattr(submitted_at, "isoformat") else str(submitted_at),
                "日付": report.report_date.isoformat() if hasattr(report.report_date, "isoformat") else str(report.report_date),
                "名前": name,
                "部署": department,
                "今週の作業内容": report.work_content or "",
                "来週の作業予定": report.next_week_plan or "",
                "会社への要望・意見": requests,
            })

        return result
