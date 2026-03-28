from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..deps import get_current_user
from ..models import InterviewRecord, Resume, User
from ..schemas import (
    ApiResponse,
    DashboardData,
    DashboardUser,
    HotJob,
    InterviewDimensionScores,
    RadarData,
    RecentInterviewRecord,
    ResumeInfo,
)

router = APIRouter(prefix="/api/v1/user", tags=["Dashboard"])


@router.get("/dashboard", response_model=ApiResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        latest_resume = await db.scalar(
            select(Resume)
            .where(Resume.user_id == current_user.id)
            .order_by(desc(Resume.updated_at), desc(Resume.id))
            .limit(1)
        )

        recent_interview_rows = (
            await db.scalars(
                select(InterviewRecord)
                .where(InterviewRecord.user_id == current_user.id)
                .order_by(desc(InterviewRecord.interview_date), desc(InterviewRecord.id))
                .limit(3)
            )
        ).all()

        if recent_interview_rows:
            n = len(recent_interview_rows)
            radar_values = [
                int(sum(r.technical_score for r in recent_interview_rows) / n),
                int(sum(r.expression_score for r in recent_interview_rows) / n),
                int(sum(r.logic_score for r in recent_interview_rows) / n),
                int(sum(r.psychology_score for r in recent_interview_rows) / n),
                int(sum(r.stability_score for r in recent_interview_rows) / n),
            ]
        else:
            radar_values = [0, 0, 0, 0, 0]

        hot_rows = (
            await db.execute(
                select(
                    InterviewRecord.job_name,
                    func.count(InterviewRecord.id).label("cnt"),
                    func.avg(InterviewRecord.score).label("avg_score"),
                )
                .group_by(InterviewRecord.job_name)
                .order_by(desc("cnt"), desc("avg_score"))
                .limit(5)
            )
        ).all()

        hot_jobs = [
            HotJob(name=name, heat=min(100, int(cnt * 20 + float(avg_score or 0) * 0.6)))
            for name, cnt, avg_score in hot_rows
        ]

        if not hot_jobs:
            hot_jobs = [
                HotJob(name="Java 开发工程师", heat=98),
                HotJob(name="前端开发工程师", heat=95),
                HotJob(name="网络工程师", heat=91),
            ]

        recent_interviews = [
            RecentInterviewRecord(
                id=row.id,
                job=row.job_name,
                score=row.score,
                date=row.interview_date,
                dimension_scores=InterviewDimensionScores(
                    technical=row.technical_score,
                    expression=row.expression_score,
                    logic=row.logic_score,
                    psychology=row.psychology_score,
                    stability=row.stability_score,
                ),
            )
            for row in recent_interview_rows
        ]

        payload = DashboardData(
            user=DashboardUser(
                user_id=current_user.id,
                name=current_user.name,
                interview_level=current_user.interview_level,
                today_practice_minutes=current_user.today_practice_minutes,
            ),
            resume=ResumeInfo(completion=latest_resume.parse_progress if latest_resume else 0),
            recent_interviews=recent_interviews,
            radar=RadarData(labels=["技术", "表达", "逻辑", "心理", "稳健"], values=radar_values),
            hot_jobs=hot_jobs,
        )

        return ApiResponse(data=payload.model_dump())
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"数据库错误: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"服务端异常: {exc}") from exc
