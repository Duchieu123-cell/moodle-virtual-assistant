from langchain_core.output_parsers import StrOutputParser
from src.modules.chat_bot.rag_bot.prompt import (
    PROMPT_REFINE,
    PROMPT_TRANSLATE,
    PROMPT_WEB_QUERY_REWRITE
)
from src.modules.chat_bot.schemas import ChatTurn, format_chat_history

from langchain_groq import ChatGroq
from src.core.config import settings

GROQ_API_KEY = settings.GROQ_API_KEY

class QueryRefiner():

    @staticmethod
    async def refine(original_query: str) -> str:
        try:
            # Nếu câu quá ngắn (< 3 từ), giữ nguyên để tránh mất ngữ nghĩa
            if len(original_query.split()) < 3:
                return original_query.strip()

            refined_query = await (
                PROMPT_REFINE |
                ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            ).ainvoke({ "input": original_query })
            
            # Fallback: Nếu LLM trả về rỗng (hiếm gặp), dùng query gốc
            if not refined_query:
                return original_query
            
            # Làm sạch chuỗi kết quả lần cuối
            return refined_query.strip().lower()
            
        except Exception as e:
            print(f"Error extracting keywords: {e}. Using original query.")
            return original_query

    @staticmethod
    async def translate(question: str) -> str:
        try:
            translated_question = await (
                PROMPT_TRANSLATE |
                ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            ).ainvoke({ "question": question })
            
            return translated_question.strip()
        except Exception as e:
            print(f"Error translating question: {e}. Using original question.")
            return question

    @staticmethod
    async def rewrite_for_web(
        question: str,
        chat_history: list[ChatTurn],
        fallback_query: str | None = None
    ) -> str:
        """
        Viết lại câu truy vấn tìm kiếm web độc lập ngữ cảnh từ lịch sử hội thoại.
        Nếu không có lịch sử hội thoại, tái sử dụng fallback_query để tiết kiệm 1 lượt gọi LLM.
        """
        base_query = (fallback_query or question).strip()
        if not chat_history:
            return base_query

        try:
            rewritten = await (
                PROMPT_WEB_QUERY_REWRITE |
                ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            ).ainvoke({
                "chat_history": format_chat_history(chat_history),
                "question": question
            })
            cleaned = rewritten.strip().strip('"').strip("'")
            return cleaned if cleaned else base_query
        except Exception as e:
            print(f"Error rewriting query for web search: {e}. Using base query.")
            return base_query