from fastapi import APIRouter
from src.modules.analyze_bot.service import AnalyzeService
from src.modules.analyze_bot.schemas import (
    AnalyzeCourseRequest, 
    AnalyzeStudentRequest
)

router = APIRouter(
    prefix="/analyze",
    tags=["Analyze Bot"]
)

@router.post(
    "/course"
)
async def analyze_course(request: AnalyzeCourseRequest):
    return await AnalyzeService.analyze_course(request)

@router.post(
    "/student"
)
async def analyze_student(request: AnalyzeStudentRequest):
    return await AnalyzeService.analyze_student(request)