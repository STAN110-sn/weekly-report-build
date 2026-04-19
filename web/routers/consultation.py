"""
相談 API（閲覧制御付き）
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user_required, require_role
from ..database import get_db
from ..models import Consultation, Member

router = APIRouter(prefix="/consultations", tags=["consultations"])

# カテゴリ定数
CATEGORY_COMPANY_GENERAL = "company_general"
CATEGORY_TO_SPECIFIC_EXEC = "to_specific_exec"


# --- Pydantic スキーマ ---


class ConsultationCreate(BaseModel):
    category: str = Field(..., pattern=f"^({CATEGORY_COMPANY_GENERAL}|{CATEGORY_TO_SPECIFIC_EXEC})$")
    content: str = Field(..., min_length=1, max_length=5000)
    is_anonymous: bool = False
    target_exec_id: Optional[int] = None  # to_specific_exec の場合に必須
    blind_to_exec_id: Optional[int] = None  # この Exec には表示しない（任意）


class ConsultationResponse(BaseModel):
    id: int
    member_id: int
    submitted_at: datetime
    category: str
    content: str
    is_anonymous: bool
    target_exec_id: Optional[int]
    blind_to_exec_id: Optional[int]
    # 投稿者名（匿名でなければ）
    author_name: Optional[str] = None

    class Config:
        from_attributes = True


def _filter_consultations_for_viewer(q, viewer: Member):
    """
    閲覧者のロールに応じて相談をフィルタ
    - employee: 自分の投稿のみ
    - executive/admin: blind_to_exec_id != viewer.id のもの（自分宛の除外相談は非表示）
    """
    if viewer.role in ("executive", "admin"):
        # 自分が閲覧対象外にされている相談は除外
        q = q.filter(
            (Consultation.blind_to_exec_id.is_(None))
            | (Consultation.blind_to_exec_id != viewer.id)
        )
    else:
        # 一般社員は自分の投稿のみ
        q = q.filter(Consultation.member_id == viewer.id)
    return q


@router.post("", response_model=ConsultationResponse, status_code=status.HTTP_201_CREATED)
def create_consultation(
    payload: ConsultationCreate,
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    """
    相談を投稿
    - company_general: 会社全般への要望・意見（全 Exec 閲覧可）
    - to_specific_exec: 特定 Exec への要望・相談（target_exec_id 必須、blind_to_exec_id で閲覧除外可）
    """
    if payload.category == CATEGORY_TO_SPECIFIC_EXEC and not payload.target_exec_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="特定Exec向けの場合は target_exec_id を指定してください",
        )

    # target_exec が存在し executive/admin か確認
    if payload.target_exec_id:
        target = db.query(Member).filter(
            Member.id == payload.target_exec_id,
            Member.active == True,
        ).first()
        if not target:
            raise HTTPException(status_code=400, detail="指定された Exec が見つかりません")
        if target.role not in ("executive", "admin"):
            raise HTTPException(status_code=400, detail="指定されたユーザーは Exec ではありません")

    # blind_to_exec が存在し executive/admin か確認
    if payload.blind_to_exec_id:
        blind_to = db.query(Member).filter(
            Member.id == payload.blind_to_exec_id,
            Member.active == True,
        ).first()
        if not blind_to:
            raise HTTPException(status_code=400, detail="閲覧除外対象の Exec が見つかりません")
        if blind_to.role not in ("executive", "admin"):
            raise HTTPException(status_code=400, detail="閲覧除外対象は Exec である必要があります")

    c = Consultation(
        member_id=current_user.id,
        category=payload.category,
        content=payload.content,
        is_anonymous=payload.is_anonymous,
        target_exec_id=payload.target_exec_id,
        blind_to_exec_id=payload.blind_to_exec_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    author_name = None if payload.is_anonymous else current_user.name
    return ConsultationResponse(
        id=c.id,
        member_id=c.member_id,
        submitted_at=c.submitted_at,
        category=c.category,
        content=c.content,
        is_anonymous=c.is_anonymous,
        target_exec_id=c.target_exec_id,
        blind_to_exec_id=c.blind_to_exec_id,
        author_name=author_name,
    )


@router.get("", response_model=List[ConsultationResponse])
def list_consultations(
    category: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: Member = Depends(get_current_user_required),
):
    """
    相談一覧を取得（閲覧者に応じてフィルタ済み）
    - 一般社員: 自分の投稿のみ
    - Executive/Admin: blind_to_exec_id で除外された相談のみ表示
    """
    q = db.query(Consultation)
    q = _filter_consultations_for_viewer(q, current_user)

    if category:
        q = q.filter(Consultation.category == category)

    consultations = q.order_by(Consultation.submitted_at.desc()).limit(limit).all()

    result = []
    for c in consultations:
        author_name = None if c.is_anonymous else (c.member.name if c.member else None)
        result.append(
            ConsultationResponse(
                id=c.id,
                member_id=c.member_id,
                submitted_at=c.submitted_at,
                category=c.category,
                content=c.content,
                is_anonymous=c.is_anonymous,
                target_exec_id=c.target_exec_id,
                blind_to_exec_id=c.blind_to_exec_id,
                author_name=author_name,
            )
        )
    return result


@router.get("/for-exec-broadcast")
def get_consultations_for_exec_broadcast(
    db: Session = Depends(get_db),
    current_user: Member = Depends(require_role("admin")),
):
    """
    全 Exec 向けブロードキャスト（Slack等）用に表示可能な相談のみ取得
    blind_to_exec_id が設定されている相談は除外（誰か特定の Exec には見せないため）
    """
    consultations = (
        db.query(Consultation)
        .filter(Consultation.blind_to_exec_id.is_(None))
        .order_by(Consultation.submitted_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": c.id,
            "content": c.content,
            "category": c.category,
            "author_name": None if c.is_anonymous else (c.member.name if c.member else None),
            "target_exec_id": c.target_exec_id,
        }
        for c in consultations
    ]
