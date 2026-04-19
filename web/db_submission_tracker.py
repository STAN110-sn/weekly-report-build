"""
DB ベース提出状況トラッカー（SubmissionTracker の drop-in 代替）
"""
from datetime import datetime, date
from typing import Dict, List

from sqlalchemy.orm import Session

from .models import Member, WeeklyReport


class DBSubmissionTracker:
    def __init__(self, db: Session):
        self.db = db

    def check_submission_status(
        self,
        target_friday: datetime,
        submission_end: datetime,
    ) -> Dict:
        """
        提出状況を確認し、SubmissionTracker.check_submission_status() 互換の dict を返す。
        """
        friday_date = target_friday.date() if isinstance(target_friday, datetime) else target_friday
        end_date = submission_end.date() if isinstance(submission_end, datetime) else submission_end

        active_members: List[Member] = (
            self.db.query(Member).filter(Member.active == True).all()
        )

        submitted_reports: List[WeeklyReport] = (
            self.db.query(WeeklyReport)
            .filter(
                WeeklyReport.report_date >= friday_date,
                WeeklyReport.report_date <= end_date,
            )
            .all()
        )

        submitted_member_ids = {r.member_id for r in submitted_reports if r.member_id}

        submitted = []
        not_submitted = []

        for m in active_members:
            if m.id in submitted_member_ids:
                submitted.append({
                    "名前": m.name,
                    "部署": m.department or "Other",
                    "Slack ID": m.slack_id or "",
                })
            else:
                not_submitted.append({
                    "名前": m.name,
                    "部署": m.department or "Other",
                    "Slack ID": m.slack_id or "",
                })

        return {
            "target_friday": target_friday.strftime("%Y-%m-%d") if isinstance(target_friday, datetime) else str(target_friday),
            "submission_end": submission_end.strftime("%Y-%m-%d") if isinstance(submission_end, datetime) else str(submission_end),
            "total_members": len(active_members),
            "submitted_count": len(submitted),
            "not_submitted_count": len(not_submitted),
            "submitted": submitted,
            "not_submitted": not_submitted,
            "submission_rate": (len(submitted) / len(active_members) * 100) if active_members else 0,
        }

    def get_status_summary_for_slack(self, status: Dict) -> Dict:
        """
        SubmissionTracker.get_status_summary_for_slack() 互換の dict を返す。
        """
        not_submitted_names = [m["名前"] for m in status.get("not_submitted", [])]
        submitted_names = [m["名前"] for m in status.get("submitted", [])]

        return {
            "target_friday": status.get("target_friday"),
            "total_members": status.get("total_members", 0),
            "submitted_count": status.get("submitted_count", 0),
            "not_submitted_count": status.get("not_submitted_count", 0),
            "submission_rate": status.get("submission_rate", 0),
            "submitted_names": submitted_names,
            "not_submitted_names": not_submitted_names,
        }
