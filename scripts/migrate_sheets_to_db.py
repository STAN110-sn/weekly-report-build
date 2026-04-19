"""
Google Sheets → DB 一括移行スクリプト
実行: python scripts/migrate_sheets_to_db.py
Heroku: heroku run python scripts/migrate_sheets_to_db.py
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web.database import get_db_context, init_db
from web.models import Member, WeeklyReport


def normalize_name(name: str) -> str:
    return name.strip().lstrip("@").strip()


def main():
    print("DB 初期化...")
    init_db()

    try:
        from spreadsheet import SpreadsheetService
    except Exception as e:
        print(f"SpreadsheetService のインポートに失敗: {e}")
        sys.exit(1)

    svc = SpreadsheetService()

    # 1. メンバー同期
    print("\n--- メンバー同期 ---")
    sheet_members = svc.get_members()
    member_created = 0
    member_updated = 0

    with get_db_context() as db:
        for m in sheet_members or []:
            name = normalize_name(m.get("名前") or "")
            if not name:
                continue
            email = (m.get("メール") or m.get("Email") or "").strip() or None
            slack_id = (m.get("Slack ID") or m.get("slack_user_id") or "").strip() or None
            department = (m.get("部署") or "Other").strip() or "Other"

            existing = None
            if email:
                existing = db.query(Member).filter(Member.email == email).first()
            if not existing:
                existing = db.query(Member).filter(Member.name == name).first()

            if existing:
                existing.department = department
                existing.slack_id = slack_id or existing.slack_id
                existing.active = True
                member_updated += 1
            else:
                db.add(Member(
                    name=name,
                    email=email,
                    department=department,
                    slack_id=slack_id,
                    role="employee",
                    active=True,
                ))
                member_created += 1

    print(f"メンバー: 新規 {member_created} 件、更新 {member_updated} 件")

    # 2. 週報移行
    print("\n--- 週報移行 ---")
    try:
        all_reports = svc.get_all_reports()
    except AttributeError:
        print("SpreadsheetService.get_all_reports() が未実装のため週報移行をスキップ")
        all_reports = []

    inserted = 0
    skipped = 0
    not_matched = 0

    with get_db_context() as db:
        members = db.query(Member).all()
        name_to_member = {m.name: m for m in members}

        for row in all_reports or []:
            raw_name = row.get("名前") or row.get("submitter_name") or ""
            norm_name = normalize_name(raw_name)
            member = name_to_member.get(norm_name)

            date_str = row.get("日付") or row.get("タイムスタンプ") or ""
            try:
                report_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            except Exception:
                print(f"日付パースエラー（スキップ）: {date_str!r}")
                skipped += 1
                continue

            member_id = member.id if member else None

            if not member:
                not_matched += 1

            # 重複チェック
            q = db.query(WeeklyReport).filter(
                WeeklyReport.report_date == report_date,
                WeeklyReport.source == "sheets_import",
            )
            if member_id:
                q = q.filter(WeeklyReport.member_id == member_id)
            else:
                q = q.filter(WeeklyReport.submitter_name == norm_name)
            if q.first():
                skipped += 1
                continue

            db.add(WeeklyReport(
                member_id=member_id,
                report_date=report_date,
                work_content=row.get("今週の作業内容") or "",
                next_week_plan=row.get("来週の作業予定") or "",
                requests_opinions=row.get("会社への要望・意見") or "",
                source="sheets_import",
                submitter_name=norm_name if not member else None,
                submitted_at=datetime.utcnow(),
            ))
            inserted += 1

    print(f"週報: 挿入 {inserted} 件、スキップ {skipped} 件、メンバー未マッチ {not_matched} 件")
    print("\n移行完了。再実行しても冪等です。")


if __name__ == "__main__":
    main()
