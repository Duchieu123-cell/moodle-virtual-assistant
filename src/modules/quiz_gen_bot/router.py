from fastapi import APIRouter, File, UploadFile, Form
from src.modules.quiz_gen_bot.service import QuizGenService
from typing import Optional

router = APIRouter(
    tags=["Quiz Generation Bot"]
)

@router.post("/generate_quiz")
async def generate_quiz(
    prompt: str = Form(""),
    num_easy: int = Form(5),
    num_medium: int = Form(5),
    num_hard: int = Form(5),
    file: Optional[UploadFile] = File(None) # Nhận file gốc từ Moodle
):
    return await QuizGenService.quiz_generate_process(prompt, num_easy, num_medium, num_hard, file)

