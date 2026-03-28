from datetime import date

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: dict


class DashboardUser(BaseModel):
    user_id: int
    name: str
    interview_level: str
    today_practice_minutes: int


class ResumeInfo(BaseModel):
    completion: int = Field(ge=0, le=100)


class InterviewDimensionScores(BaseModel):
    technical: int
    expression: int
    logic: int
    psychology: int
    stability: int


class RecentInterviewRecord(BaseModel):
    id: int
    job: str
    score: int
    date: date
    dimension_scores: InterviewDimensionScores


class RadarData(BaseModel):
    labels: list[str]
    values: list[int]


class HotJob(BaseModel):
    name: str
    heat: int = Field(ge=0, le=100)


class DashboardData(BaseModel):
    user: DashboardUser
    resume: ResumeInfo
    recent_interviews: list[RecentInterviewRecord]
    radar: RadarData
    hot_jobs: list[HotJob]
