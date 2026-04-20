"""
JWT 認証ヘルパー（Cookie + Bearer 対応）
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import Member

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


def create_jwt(member_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(member_id), "email": email, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _member_from_payload(payload: dict, db: Session) -> Optional[Member]:
    member_id = payload.get("sub")
    if not member_id:
        return None
    return db.query(Member).filter(Member.id == int(member_id), Member.active == True).first()


def _dev_member() -> Member:
    """DEV_BYPASS_AUTH=true 時に使う仮の admin ユーザー（DB 不使用）"""
    m = Member()
    m.id = 0
    m.name = "Dev Admin"
    m.email = "dev@localhost"
    m.role = "admin"
    m.active = True
    m.department = "Development"
    m.slack_id = None
    return m


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[Member]:
    from config import config as _cfg
    if _cfg.DEV_BYPASS_AUTH:
        return _dev_member()
    token = _extract_token(request)
    if not token:
        return None
    payload = decode_jwt(token)
    if not payload:
        return None
    return _member_from_payload(payload, db)


async def get_current_user_required(
    current_user: Optional[Member] = Depends(get_current_user),
) -> Member:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="認証が必要です",
        )
    return current_user


def require_role(*allowed_roles: str):
    async def role_checker(
        current_user: Member = Depends(get_current_user_required),
    ) -> Member:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"この操作には {', '.join(allowed_roles)} 権限が必要です",
            )
        return current_user

    return role_checker


def require_admin(current_user: Member = Depends(get_current_user_required)) -> Member:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="管理者権限が必要です")
    return current_user
