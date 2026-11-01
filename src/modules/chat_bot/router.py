from src.modules.chat_bot.service import ChatService
from src.modules.chat_bot.schemas import Message
from fastapi import APIRouter, HTTPException, status
from src.modules.chat_bot.query_bot.schemas import (
    SQLGenerationRequest,
    AnswerGenerationRequest
)

router = APIRouter(
    tags=["Chat Bot"]
)

@router.post(
    "/chat",
    description="Moodle gọi API này để chat chủ động"
)
async def chat(data: Message):
    try:
        return await ChatService.chat(data)

    except Exception as e:
        print(f"Dịch vụ chat gặp sự cố: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Dịch vụ chat gặp sự cố: {e}"
        )

@router.post(
    "/fix_sql",
    description="Moodle gọi API này để lấy mã SQL cần chạy"
)
async def get_sql(request: SQLGenerationRequest):
    try:
        return await ChatService.generate_sql(request)
    
    except Exception as e:
        print(f"Gặp sự cố khi tạo mã SQL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Gặp sự cố khi tạo mã SQL: {e}"
        )

@router.post(
    "/get_sql_answer",
    description="Moodle chạy SQL xong, ném data vào API này để lấy câu trả lời"
)
async def get_sql_answer(request: AnswerGenerationRequest):
    try:
        return await ChatService.generate_answer(request)
    
    except Exception as e:
        print(f"Gặp sự cố khi tạo câu trả lời cho câu truy vấn: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Gặp sự cố khi tạo câu trả lời cho câu truy vấn: {e}"
        )
    