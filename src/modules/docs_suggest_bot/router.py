from src.modules.docs_suggest_bot.service import DocsSuggestService
from src.modules.docs_suggest_bot.schemas import Quizzes
from fastapi import HTTPException, status, APIRouter

router = APIRouter(
    tags=["Docs Suggest Bot"]
)

@router.post("/docs_suggest")
async def get_docs_suggest(request: Quizzes):
    try:
        return await DocsSuggestService.check_docs(request)
    
    except Exception as e:
        print(f"Có lỗi khi khi đề xuất tài liệu: {e}")
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = f"Có lỗi khi khi đề xuất tài liệu: {e}"
        )