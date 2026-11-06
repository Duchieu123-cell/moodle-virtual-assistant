from src.modules.reminder_bot.service import (
    QuizReminderService, 
    AssignReminderService
)
from src.modules.reminder_bot.schemas import (
    QuizReminderRequestItem,
    AssignReminderRequestItem
)
from fastapi import APIRouter

router = APIRouter(
    prefix="/reminder",
    tags=["Reminder Bot"]
)

@router.post("/assignment")
async def get_assignment_reminder(request: AssignReminderRequestItem):
    return await AssignReminderService.check_assignment(request)
        
@router.post("/quiz")
async def get_quiz_reminder(request: QuizReminderRequestItem):
    return await QuizReminderService.check_quiz(request)
             