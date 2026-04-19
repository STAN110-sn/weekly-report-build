"""
Google OAuth2 ログイン / コールバック / ログアウト
"""
import os
import secrets
import urllib.parse

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import create_jwt
from ..database import get_db
from ..models import Member

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = "openid email profile"


@router.get("/login")
def login(request: Request):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth が設定されていません")

    state = secrets.token_urlsafe(32)
    redirect_uri = f"{APP_BASE_URL}/auth/callback"

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = GOOGLE_AUTH_URL + "?" + urllib.parse.urlencode(params)

    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "__oauth_state",
        state,
        max_age=300,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db),
):
    if error:
        return RedirectResponse(f"/login?error={urllib.parse.quote(error)}", status_code=302)

    stored_state = request.cookies.get("__oauth_state")
    if not stored_state or stored_state != state:
        raise HTTPException(status_code=400, detail="OAuth state が一致しません")

    if not code:
        raise HTTPException(status_code=400, detail="認証コードがありません")

    redirect_uri = f"{APP_BASE_URL}/auth/callback"
    token_resp = http_requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if not token_resp.ok:
        raise HTTPException(status_code=400, detail="トークン取得に失敗しました")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="アクセストークンが取得できません")

    userinfo_resp = http_requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not userinfo_resp.ok:
        raise HTTPException(status_code=400, detail="ユーザー情報の取得に失敗しました")

    userinfo = userinfo_resp.json()
    email = userinfo.get("email")
    name = userinfo.get("name") or email

    if not email:
        raise HTTPException(status_code=400, detail="メールアドレスが取得できません")

    member = db.query(Member).filter(Member.email == email).first()
    if not member:
        member = Member(name=name, email=email, role="employee", active=True)
        db.add(member)
        db.commit()
        db.refresh(member)
    elif not member.active:
        raise HTTPException(status_code=403, detail="このアカウントは無効化されています")

    jwt_token = create_jwt(member.id, member.email)

    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("__oauth_state")
    response.set_cookie(
        "access_token",
        jwt_token,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="lax",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response


@router.get("/logout")
def logout_get():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("access_token")
    return response
