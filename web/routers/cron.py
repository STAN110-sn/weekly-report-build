"""
外部 cron（GitHub Actions 等）から定期的に叩く tick エンドポイント。
共有シークレット CRON_TOKEN で認証。
"""
import os
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.scheduler_service import run_due_schedules

router = APIRouter(prefix="/internal/cron", tags=["cron"])


def _verify_token(authorization: str | None) -> None:
    expected = os.getenv("CRON_TOKEN", "")
    if not expected:
        # サーバ側に CRON_TOKEN が未設定の場合は誤って認証無しで動かないよう拒否
        raise HTTPException(status_code=503, detail="CRON_TOKEN is not configured on the server")
    if not authorization or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="invalid or missing CRON_TOKEN")


@router.post("/tick")
def tick(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    GitHub Actions から定期実行され、発火時刻に達したスケジュールを実行する。

    認証: `Authorization: Bearer $CRON_TOKEN` ヘッダ必須。
    """
    _verify_token(authorization)
    return run_due_schedules(db)
