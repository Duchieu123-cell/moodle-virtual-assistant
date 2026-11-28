from langchain_core.output_parsers import StrOutputParser
from src.modules.chat_bot.talk_bot.prompt import PROMPT_TALK
from langchain_groq import ChatGroq
from src.core.config import settings
from src.modules.chat_bot.schemas import (
    format_chat_history,
    ChatTurn
)
from src.core.exception import InternalServerError
import logging

GROQ_API_KEY = settings.GROQ_API_KEY
logger = logging.getLogger(__name__)

class TalkService():
    
    @staticmethod
    async def talk(user_msg: str, chat_history: list[ChatTurn]):
        try:
            chain = (
                PROMPT_TALK | 
                ChatGroq( 
                    model_name="openai/gpt-oss-20b",
                    temperature=0.7,
                    groq_api_key=GROQ_API_KEY
                ) | 
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "chat_history": format_chat_history(chat_history),
                "input": user_msg
            })
        except Exception as e:
            logger.exception("Failed to generate talk response for user message: %s", user_msg)
            raise InternalServerError(
                message=f"Failed to generate talk response for user message: {user_msg}",
                type="talk_error"
            )
        
        logger.info("Finished generating talk response for user message: %s", user_msg)
        
        return { "response": response, "type": "talk" }