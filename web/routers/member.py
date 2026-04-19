"""
メンバー管理 API
名簿の CRUD、Google Sheets からのデータ移行
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user_required, require_role
from ..database import get_db
from ..models import Member

router = APIRouter(prefix="/members", tags=["members"])


# --- Pydantic スキーマ ---


class MemberBase(BaseModel):
    name: str
    email: Optional[str] = None
    department: str = "Other"
    role: str = "employee"
    slack_id: Optional[str] = None
    active: bool = True


class MemberCreate(MemberBase):
    pass


class MemberUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None
    slack_id: Optional[str] = None
    active: Optional[bool] = None


class MemberResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    department: str
    role: str
    slack_id: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True


# --- API エンドポイント ---


@router.get("", response_model=List[MemberResponse])
def list_members(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    """
    メンバー一覧を取得
    - 一般社員: active なメンバーのみ
    - admin/executive: 全メンバー（active_only=false で）
    """
    q = db.query(Member)
    if active_only:
        q = q.filter(Member.active == True)
    members = q.order_by(Member.name).all()

    # 一般社員は自分と同僚の基本情報のみ（email はマスク等のポリシーに応じて調整可）
    if current_user.role == "employee":
        return [MemberResponse.model_validate(m) for m in members]

    return [MemberResponse.model_validate(m) for m in members]


@router.get("/me", response_model=MemberResponse)
def get_me(current_user: Member = Depends(get_current_user_required)):
    """ログインユーザー自身の情報"""
    return MemberResponse.model_validate(current_user)


@router.get("/executives", response_model=List[MemberResponse])
def list_executives(
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    """Executive ロールのメンバー一覧（相談の「対象Exec」「閲覧除外」選択用）"""
    members = (
        db.query(Member)
        .filter(Member.role.in_(["executive", "admin"]), Member.active == True)
        .order_by(Member.name)
        .all()
    )
    return [MemberResponse.model_validate(m) for m in members]


@router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_role("admin")),
):
    """メンバーを新規作成（admin のみ）"""
    if payload.email and db.query(Member).filter(Member.email == payload.email).first():
        raise HTTPException(status_code=400, detail="このメールアドレスは既に登録されています")
    member = Member(**payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return MemberResponse.model_validate(member)


@router.patch("/{member_id}", response_model=MemberResponse)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_role("admin")),
):
    """メンバーを更新（admin のみ）"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="メンバーが見つかりません")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(member, k, v)
    db.commit()
    db.refresh(member)
    return MemberResponse.model_validate(member)


@router.post("/sync-from-sheets")
def sync_from_sheets(
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_role("admin")),
):
    """
    Google Sheets の名簿（Member_list / Members）から DB へ同期
    既存メンバーは名前でマッチして更新、新規は追加
    """
    import sys
    from pathlib import Path

    # 親ディレクトリをパスに追加（spreadsheet モジュールのインポート用）
    parent = Path(__file__).resolve().parent.parent.parent
    if str(parent) not in sys.path:
        sys.path.insert(0, str(parent))

    from spreadsheet import SpreadsheetService

    svc = SpreadsheetService()
    sheet_members = svc.get_members()
    if not sheet_members:
        return {"synced": 0, "created": 0, "updated": 0, "message": "名簿データがありません"}

    created = 0
    updated = 0
    for m in sheet_members:
        name = (m.get("名前") or "").strip()
        if not name:
            continue
        slack_id = (m.get("Slack ID") or m.get("slack_user_id") or "").strip()
        department = (m.get("部署") or "Other").strip() or "Other"

        existing = db.query(Member).filter(Member.name == name).first()
        if existing:
            existing.department = department
            existing.slack_id = slack_id or existing.slack_id
            existing.active = True
            updated += 1
        else:
            db.add(
                Member(
                    name=name,
                    department=department,
                    slack_id=slack_id or None,
                    role="employee",
                    active=True,
                )
            )
            created += 1

    db.commit()
    return {
        "synced": len(sheet_members),
        "created": created,
        "updated": updated,
        "message": f"同期完了: 新規 {created} 件、更新 {updated} 件",
    }
