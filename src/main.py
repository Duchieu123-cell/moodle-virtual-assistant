from src.modules.analyze_bot.router import router as analyze_router
from src.modules.chat_bot.router import router as chat_router
from src.modules.docs_suggest_bot.router import router as docs_suggest_router
from src.modules.file_upload.router import router as file_upload_router
from src.modules.quiz_gen_bot.router import router as quiz_gen_router
from src.modules.reminder_bot.router import router as reminder_router
from src.modules.status_check.router import router as status_check_router
from src.core.exception import CustomException
from starlette.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.core.config import settings


app = FastAPI(
    title=settings.PROJECT_NAME
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message
        }
    )

app.include_router(analyze_router)
app.include_router(chat_router)
app.include_router(docs_suggest_router)
app.include_router(file_upload_router)
app.include_router(quiz_gen_router)
app.include_router(reminder_router)
app.include_router(status_check_router)