from langchain_core.output_parsers import StrOutputParser
from src.modules.chat_bot.rag_bot.prompt import (
    PROMPT_REFINE, 
    PROMPT_TRANSLATE
)

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