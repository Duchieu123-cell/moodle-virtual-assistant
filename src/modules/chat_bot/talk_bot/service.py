from langchain_core.output_parsers import StrOutputParser
from src.modules.chat_bot.talk_bot.prompt import PROMPT_TALK
from langchain_groq import ChatGroq
from src.core.config import settings
from src.modules.chat_bot.schemas import (
    format_chat_history,
    ChatTurn
)

GROQ_API_KEY = settings.GROQ_API_KEY

class TalkService():
    
    @staticmethod
    async def talk(user_msg: str, chat_history: list[ChatTurn]):
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
        print("--------------------------------------------------------------------------------------------------------------")
        print("TALK RESPONSE:\n", response)
        print("--------------------------------------------------------------------------------------------------------------")
        return {
            "response": response,
            "type": "talk"
        }