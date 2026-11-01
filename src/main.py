from src.modules.analyze_bot.router import router as analyze_router
from src.modules.chat_bot.router import router as chat_router
from src.modules.docs_suggest_bot.router import router as docs_suggest_router
from src.modules.file_upload.router import router as file_upload_router
from src.modules.quiz_gen_bot.router import router as quiz_gen_router
from src.modules.reminder_bot.router import router as reminder_router
from src.modules.status_check.router import router as status_check_router
from src.core.exception_handler import CustomException, http_exception_handler
from starlette.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)


app = FastAPI(
    title= "VIRTUAL ASSISTANT"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze_router)
app.include_router(chat_router)
app.include_router(docs_suggest_router)
app.include_router(file_upload_router)
app.include_router(quiz_gen_router)
app.include_router(reminder_router)
app.include_router(status_check_router)

app.add_exception_handler(CustomException, http_exception_handler)