from pydantic import BaseModel
from typing import Any
from src.modules.chat_bot.schemas import ChatTurn

class SQLGenerationRequest(BaseModel):
    message: str
    user_id: int
    role: str # 'student' hoặc 'teacher'
    chat_history: list[ChatTurn] = []
    previous_error_sql: str | None = None
    sql_error_msg: str | None = None

class AnswerGenerationRequest(BaseModel):
    message: str
    sql_result: list[Any]  # Nhận kết quả dạng list từ Moodle gửi sang
    chat_history: list[ChatTurn] = []