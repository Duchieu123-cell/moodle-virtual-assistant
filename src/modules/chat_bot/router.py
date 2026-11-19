from src.modules.chat_bot.service import ChatService
from src.modules.chat_bot.schemas import Message
from fastapi import APIRouter
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
    return await ChatService.chat(data)

@router.post(
    "/fix_sql",
    description="Moodle gọi API này để lấy mã SQL cần chạy"
)
async def get_sql(request: SQLGenerationRequest):
    return await ChatService.generate_sql(request)

@router.post(
    "/get_sql_answer",
    description="Moodle chạy SQL xong, ném data vào API này để lấy câu trả lời"
)
async def get_sql_answer(request: AnswerGenerationRequest):
    return await ChatService.generate_answer(request)