from src.modules.intent_classifier.main import IntentClassifierSingleton
from src.modules.chat_bot.query_bot.schemas import (
    SQLGenerationRequest,
    AnswerGenerationRequest
)
from src.modules.chat_bot.schemas import Message
from src.modules.chat_bot.query_bot.service import QueryService
from src.modules.chat_bot.talk_bot.service import TalkService
from src.modules.chat_bot.rag_bot.service import RagService


class ChatService():
    intent_classifier = IntentClassifierSingleton.get()
 
    @staticmethod
    async def chat(data: Message):
        user_msg = data.message
    
        # 1. Phân loại Intent bằng Machine Learning (Nhanh & Chính xác)
        print("-"*60)
        print(f"Analyzing intent for: '{user_msg}'")
        role = ChatService.intent_classifier.predict(user_msg)
        print(f"DETECTED ROLE: {role}")
        print("-"*60)
        # 2. Định tuyến (Routing)
        
        if role == 1:
            # Intent: Hỏi kiến thức (RAG)
            return await RagService.rag(user_msg, data.chat_history)
            
        elif role == 2:
            # Intent: Hỏi thông tin cá nhân/DB (Query)
            return await QueryService.generate_sql(
                SQLGenerationRequest(
                    message = user_msg,
                    user_id = data.user_id,
                    role = data.role,
                    chat_history = data.chat_history
                )
            )
            
        elif role == 3:
            # Intent: Chitchat/System Info (Talk)
            return await TalkService.talk(user_msg, data.chat_history)

        else:
            return await TalkService.talk(user_msg, data.chat_history)

    @staticmethod
    async def generate_sql(request: SQLGenerationRequest):
        return await QueryService.generate_sql(request)
 
    @staticmethod
    async def generate_answer(request: AnswerGenerationRequest):
        return await QueryService.generate_answer(request)