"""
SQLAlchemy ORM モデル
週報・相談管理システムのデータスキーマ
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class Member(Base):
    """メンバー（名簿）テーブル"""

    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, index=True)
    department = Column(String(100), default="Other")
    role = Column(String(50), default="employee")  # employee | executive | admin
    slack_id = Column(String(50))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    weekly_reports = relationship("WeeklyReport", back_populates="member", foreign_keys="WeeklyReport.member_id")
    consultations = relationship("Consultation", back_populates="member", foreign_keys="Consultation.member_id")
    consultations_blind_to = relationship(
        "Consultation",
        back_populates="blind_to_exec",
        foreign_keys="Consultation.blind_to_exec_id",
    )
    consultations_target = relationship(
        "Consultation",
        back_populates="target_exec",
        foreign_keys="Consultation.target_exec_id",
    )


class WeeklyReport(Base):
    """週報テーブル"""

    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    report_date = Column(Date, nullable=False)
    work_content = Column(Text)
    next_week_plan = Column(Text)
    requests_opinions = Column(Text)
    company_feedback = Column(Text)  # 旧形式互換
    source = Column(String(50), default="web")  # web | sheets_import
    submitted_at = Column(DateTime, default=datetime.utcnow)
    submitter_name = Column(String(100), nullable=True)  # sheets_import 用

    member = relationship("Member", back_populates="weekly_reports", foreign_keys=[member_id])


class GeneratedReport(Base):
    """AI生成レポートテーブル"""

    __tablename__ = "generated_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_type = Column(String(50), nullable=False)  # general | executive
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    markdown_content = Column(Text)
    google_doc_url = Column(String(500))
    google_pdf_url = Column(String(500))
    total_reports = Column(Integer, default=0)
    model_used = Column(String(100))
    generated_at = Column(DateTime, default=datetime.utcnow)


class Consultation(Base):
    """相談テーブル（閲覧制御付き）"""

    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    category = Column(String(50), nullable=False)  # company_general | to_specific_exec
    content = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=False)
    blind_to_exec_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    target_exec_id = Column(Integer, ForeignKey("members.id"), nullable=True)

    member = relationship("Member", back_populates="consultations", foreign_keys=[member_id])
    blind_to_exec = relationship(
        "Member",
        back_populates="consultations_blind_to",
        foreign_keys=[blind_to_exec_id],
    )
    target_exec = relationship(
        "Member",
        back_populates="consultations_target",
        foreign_keys=[target_exec_id],
    )


class ReportSchedule(Base):
    """レポート定期実行スケジュール"""

    __tablename__ = "report_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    report_type = Column(String(20), default="both")  # general | executive | both
    days_of_week = Column(String(20), nullable=False)  # CSV "0,3" Mon=0..Sun=6
    hour = Column(Integer, nullable=False)
    minute = Column(Integer, nullable=False)
    timezone = Column(String(50), default="Asia/Tokyo")
    enabled = Column(Boolean, default=True)
    next_run_at = Column(DateTime, nullable=True, index=True)  # UTC
    last_run_at = Column(DateTime, nullable=True)  # UTC
    last_run_status = Column(String(500), nullable=True)
    created_by_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship("Member", foreign_keys=[created_by_id])
