from datetime import date

from fastapi import FastAPI
from sqlalchemy import func, select

from .api.dashboard import router as dashboard_router
from .database import AsyncSessionLocal, Base, engine
from .models import InterviewRecord, Resume, User

app = FastAPI(title="AI 模拟面试平台 API", version="0.1.0")
app.include_router(dashboard_router)


@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        user_count = await session.scalar(select(func.count(User.id)))
        if user_count == 0:
            user = User(name="林同学", interview_level="面试达人", today_practice_minutes=102)
            session.add(user)
            await session.flush()

            resume = Resume(
                user_id=user.id,
                file_path="uploads/demo_resume.pdf",
                structured_content={"skills": ["Python", "FastAPI", "SQLAlchemy"]},
                parse_progress=82,
            )
            session.add(resume)

            records = [
                InterviewRecord(
                    user_id=user.id,
                    job_name="前端开发",
                    score=89,
                    interview_date=date(2026, 3, 18),
                    technical_score=88,
                    expression_score=82,
                    logic_score=90,
                    psychology_score=80,
                    stability_score=86,
                ),
                InterviewRecord(
                    user_id=user.id,
                    job_name="Java 开发",
                    score=84,
                    interview_date=date(2026, 3, 16),
                    technical_score=85,
                    expression_score=80,
                    logic_score=86,
                    psychology_score=78,
                    stability_score=83,
                ),
                InterviewRecord(
                    user_id=user.id,
                    job_name="网络工程师",
                    score=87,
                    interview_date=date(2026, 3, 12),
                    technical_score=89,
                    expression_score=81,
                    logic_score=88,
                    psychology_score=79,
                    stability_score=85,
                ),
            ]
            session.add_all(records)
            await session.commit()


@app.get("/health")
async def health():
    return {"status": "running"}
