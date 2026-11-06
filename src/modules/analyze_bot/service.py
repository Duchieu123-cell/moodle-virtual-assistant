from src.modules.analyze_bot.prompt import (
    PROMPT_ANALYZE_COURSE_PROGRESS, 
    PROMPT_ANALYZE_STUDENT_PROGRESS    
)    
from src.modules.analyze_bot.schemas import (
    AnalyzeCourseRequest,
    AnalyzeStudentRequest
)
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from src.core.config import settings
from src.core.exception import InternalServerError


class AnalyzeService():

    @staticmethod
    async def analyze_course(input: AnalyzeCourseRequest):
        try:
            chain = (
                PROMPT_ANALYZE_COURSE_PROGRESS |
                ChatGroq(
                    model_name="openai/gpt-oss-safeguard-20b",
                    temperature=0,
                    groq_api_key=settings.GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "course_name": input.course_name,
                "overall_statistics": input.model_dump_json(indent=2, exclude={"course_name"}), 
            })
        except Exception:
            raise InternalServerError("Lỗi xảy ra khi phân tích tiến trình khóa học. Vui lòng thử lại sau.")
            
        print("-"*100)
        print("ANALYZE COURSE RESPONSE:\n", response)
        print("-"*100)
        return {
            "response": response
        }
    
    @staticmethod
    async def analyze_student(input: AnalyzeStudentRequest):
        try:
            chain = (
                PROMPT_ANALYZE_STUDENT_PROGRESS |
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    temperature=0.7,
                    groq_api_key=settings.GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "course_name": input.course_name,
                "course_type": input.course_type,
                "progress_data": input.model_dump_json(indent=2, exclude={"course_name"}),
            })
        except Exception:
            raise InternalServerError("Lỗi xảy ra khi phân tích tiến trình sinh viên. Vui lòng thử lại sau.")
        
        print("-"*100)
        print("ANALYZE STUDENT RESPONSE:\n", response)
        print("-"*100)
        return {
            "response": response
        }