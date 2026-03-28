from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    interview_level: Mapped[str] = mapped_column(String(32), nullable=False, default="面试新人")
    today_practice_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    interview_records = relationship(
        "InterviewRecord", back_populates="user", cascade="all, delete-orphan"
    )


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    structured_content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parse_progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="resumes")


class InterviewRecord(Base):
    __tablename__ = "interview_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_name: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    interview_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 五个维度
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False)
    expression_score: Mapped[int] = mapped_column(Integer, nullable=False)
    logic_score: Mapped[int] = mapped_column(Integer, nullable=False)
    psychology_score: Mapped[int] = mapped_column(Integer, nullable=False)
    stability_score: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="interview_records")
