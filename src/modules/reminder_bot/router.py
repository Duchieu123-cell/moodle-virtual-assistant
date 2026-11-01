from src.modules.reminder_bot.service import (
    QuizReminderService, 
    AssignReminderService
)
from src.modules.reminder_bot.schemas import (
    QuizReminderRequestItem,
    AssignReminderRequestItem
)
from fastapi import HTTPException, status, APIRouter

router = APIRouter(
    prefix="/reminder",
    tags=["Reminder Bot"]
)

@router.post("/assignment")
async def get_assignment_reminder(request: AssignReminderRequestItem):
    try:
        return await AssignReminderService.check_assignment(request)

    except Exception as e:
        print(f"Lỗi trong khi tạo nhắc nhở assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Lỗi trong khi tạo nhắc nhở assignment: {e}"
        )
        
@router.post("/quiz")
async def get_quiz_reminder(request: QuizReminderRequestItem):
    try:
        return await QuizReminderService.check_quiz(request)

    except Exception as e:
        print(f"Lỗi trong khi tạo nhắc nhở quiz: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Lỗi trong khi tạo nhắc nhở quiz: {e}"
        )
             