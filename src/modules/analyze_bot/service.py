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
import logging

logger = logging.getLogger(__name__)

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
        except Exception as e:
            logger.exception("Failed to analyze course %s", input.course_name)
            raise InternalServerError(
                message=f"Failed to analyze course {input.course_name}",
                type="analyze_course_error"
            )
            

        logger.info("Finished analyzing course %s", input.course_name)
        
        return { "response": response }
    
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
        except Exception as e:
            logger.exception("Failed to analyze student %s in course %s", input.student_name, input.course_name)
            raise InternalServerError(
                message=f"Failed to analyze student {input.student_name} in course {input.course_name}",
                type="analyze_student_error"
            )
        
        logger.info("Finished analyzing student %s in course %s", input.student_name, input.course_name)

        return { "response": response }