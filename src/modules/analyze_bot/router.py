from fastapi import HTTPException, status, APIRouter
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
    try:
        return await AnalyzeService.analyze_course(request)
       
    except Exception as e:
        print(f"Có lỗi khi phân tích tiến độ khóa học: {e}")
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"Có lỗi xảy ra khi phân tích tiến độ khóa học: {e}"
        )

@router.post(
    "/student"
)
async def analyze_student(request: AnalyzeStudentRequest):
    try:
        return await AnalyzeService.analyze_student(request)
    
    except Exception as e:
        print(f"Có lỗi khi phân tích sinh viên: {e}")
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail = f"Có lỗi xảy ra khi phân tích tiến độ sinh viên: {e}"
        )