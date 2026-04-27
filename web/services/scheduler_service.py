"""
レポート定期実行スケジューリングロジック

- compute_next_run_at: 次回発火時刻を UTC で計算
- run_due_schedules: tick リクエスト時に呼び出され、発火時刻が来たスケジュールを実行
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import ReportSchedule
from .report_runner import run_weekly_report

logger = logging.getLogger(__name__)


def parse_days_of_week(csv: str) -> list[int]:
    """'0,3,5' -> [0,3,5]。空や不正値は無視。"""
    out: list[int] = []
    for token in (csv or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            v = int(token)
        except ValueError:
            continue
        if 0 <= v <= 6:
            out.append(v)
    return sorted(set(out))


def compute_next_run_at(schedule: ReportSchedule, now_utc: datetime | None = None) -> datetime | None:
    """
    schedule の (days_of_week, hour, minute, timezone) に基づき、
    now_utc より後で最も近い発火時刻を UTC で返す。
    候補曜日が空なら None。
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)

    days = parse_days_of_week(schedule.days_of_week or "")
    if not days:
        return None

    try:
        tz = ZoneInfo(schedule.timezone or "Asia/Tokyo")
    except Exception:
        tz = ZoneInfo("Asia/Tokyo")

    now_local = now_utc.astimezone(tz)

    # 今日から最大 7 日先まで候補を生成し、最初に now より後のものを返す
    for offset in range(0, 8):
        candidate_date = (now_local + timedelta(days=offset)).date()
        weekday = candidate_date.weekday()  # Mon=0..Sun=6
        if weekday not in days:
            continue
        candidate_local = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            int(schedule.hour),
            int(schedule.minute),
            tzinfo=tz,
        )
        if candidate_local > now_local:
            return candidate_local.astimezone(timezone.utc).replace(tzinfo=None)

    return None


def _select_due_schedules(db: Session, now_utc_naive: datetime, dialect: str) -> list[ReportSchedule]:
    """
    発火時刻が来たスケジュールを取得（可能なら排他ロック）。
    Postgres: FOR UPDATE SKIP LOCKED
    SQLite: 単純 SELECT（dev 用、シングルプロセス前提）
    """
    if dialect == "postgresql":
        rows = (
            db.query(ReportSchedule)
            .filter(ReportSchedule.enabled == True)  # noqa: E712
            .filter(ReportSchedule.next_run_at != None)  # noqa: E711
            .filter(ReportSchedule.next_run_at <= now_utc_naive)
            .with_for_update(skip_locked=True)
            .all()
        )
    else:
        rows = (
            db.query(ReportSchedule)
            .filter(ReportSchedule.enabled == True)  # noqa: E712
            .filter(ReportSchedule.next_run_at != None)  # noqa: E711
            .filter(ReportSchedule.next_run_at <= now_utc_naive)
            .all()
        )
    return rows


def _run_one(db: Session, schedule: ReportSchedule, now_utc_naive: datetime) -> dict:
    """1スケジュールを実行し、結果を schedule に書き戻す。例外は飲み込まず status に残す。"""
    started_at = now_utc_naive
    try:
        result = run_weekly_report(schedule.report_type or "both")
        schedule.last_run_at = started_at
        schedule.last_run_status = "success"
        outcome = {"id": schedule.id, "name": schedule.name, "status": "success", "result": result}
    except Exception as e:
        logger.exception("schedule %s run failed", schedule.id)
        schedule.last_run_at = started_at
        msg = f"failed: {type(e).__name__}: {e}"
        schedule.last_run_status = msg[:500]
        outcome = {"id": schedule.id, "name": schedule.name, "status": "failed", "error": str(e)}
    finally:
        # 必ず next_run_at を未来に進める（失敗時に永遠にループしないため）
        schedule.next_run_at = compute_next_run_at(schedule, datetime.now(timezone.utc))
    return outcome


def run_due_schedules(db: Session) -> dict:
    """発火時刻に達したスケジュールを順次実行。tick エンドポイントから呼ばれる。"""
    now_utc_naive = datetime.utcnow()
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

    fired: list[dict] = []
    errors: list[dict] = []

    due = _select_due_schedules(db, now_utc_naive, dialect)
    for schedule in due:
        outcome = _run_one(db, schedule, now_utc_naive)
        if outcome["status"] == "success":
            fired.append(outcome)
        else:
            errors.append(outcome)

    db.commit()

    return {
        "fired": len(fired),
        "errors": len(errors),
        "details": {"fired": fired, "errors": errors},
        "checked_at": now_utc_naive.isoformat() + "Z",
    }


def refresh_next_run_at(schedule: ReportSchedule) -> None:
    """admin CRUD から呼ばれる。create / update 時に next_run_at を再計算。"""
    if not schedule.enabled:
        schedule.next_run_at = None
        return
    schedule.next_run_at = compute_next_run_at(schedule, datetime.now(timezone.utc))
