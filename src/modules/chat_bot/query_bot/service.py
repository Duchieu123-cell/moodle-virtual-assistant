from src.modules.chat_bot.query_bot.prompt import PROMPT_SQL_QUERY, PROMPT_FIX_BUG, PROMPT_SQL_ANSWER, STUDENT_CONSTRAINT, TEACHER_CONSTRAINT
from src.modules.chat_bot.query_bot.schemas import (
    SQLGenerationRequest, 
    AnswerGenerationRequest
)
from langchain_core.output_parsers import StrOutputParser
from src.modules.chat_bot.schemas import format_chat_history
from src.modules.chat_bot.query_bot.table_info import table_info
from langchain_groq import ChatGroq
import re
from src.core.config import settings
from src.core.exception import InternalServerError
import logging

GROQ_API_KEY = settings.GROQ_API_KEY
logger = logging.getLogger(__name__)

class QueryService():
    
    @staticmethod
    async def generate_sql(request: SQLGenerationRequest):
        """Bước 1: Chuyển đổi tin nhắn thành câu lệnh SQL hoặc Sửa lỗi SQL"""
        pattern = r"SELECT.*?;"
        if request.role.lower() == 'student':
            current_role_constraint = STUDENT_CONSTRAINT
        else:
            current_role_constraint = TEACHER_CONSTRAINT
            
        # NẾU MOODLE BÁO LỖI SQL (Quay lại sửa lỗi)
        if request.previous_error_sql and request.sql_error_msg:          
            try:
                chain = (
                    PROMPT_FIX_BUG |
                    ChatGroq(
                        model_name="qwen/qwen3.8-27b",
                        temperature=0,
                        groq_api_key=GROQ_API_KEY
                    ) |
                    StrOutputParser()
                )
                execute_query = await chain.ainvoke({
                    "chat_history": format_chat_history(request.chat_history),
                    "role_constraint": current_role_constraint,
                    "user_id": request.user_id,
                    "question": request.message,
                    "database_structure": table_info,
                    "previous_error_sql_code": request.previous_error_sql,
                    "error": request.sql_error_msg
                })
                
            except Exception as e:
                logger.exception("Failed to fix SQL")
                raise InternalServerError(
                    message=f"Failed to fix SQL: {str(e)}",
                    type="fix_sql_error"
                )
            
        # NẾU LÀ LẦN ĐẦU TIÊN TẠO SQL
        else:
            try:
                chain = (
                    PROMPT_SQL_QUERY |
                    ChatGroq(
                        model_name="openai/gpt-oss-120b",
                        temperature=0,
                        groq_api_key=GROQ_API_KEY
                    ) |
                    StrOutputParser()
                )
                execute_query = await chain.ainvoke({
                    "chat_history": format_chat_history(request.chat_history),
                    "role_constraint": current_role_constraint,
                    "user_id": request.user_id,
                    "question": request.message,
                    "database_structure": table_info 
                })
                                
            except Exception as e:
                logger.exception("Failed to generate SQL")
                raise InternalServerError(
                    message=f"Failed to generate SQL: {str(e)}",
                    type="generate_sql_error"
                )

        # Trích xuất đúng câu lệnh SQL
        sql_code = re.findall(pattern, execute_query, re.DOTALL)[0]
        
        # OUTPUT VALIDATION (Kiểm duyệt lớp 2 - Chốt chặn an toàn)
        if request.role.lower() == 'student':
            # Đảm bảo mã SQL của sinh viên phải chứa thông tin lọc theo ID của họ
            # Ví dụ: kiểm tra xem id của user có xuất hiện trong chuỗi SQL không
            if str(request.user_id) not in sql_code:
                logger.warning("LLM sinh SQL không có bộ lọc ID cho student!")
                print("-"*100)
                
                # Vẫn trả về response nhưng là nội dung báo lỗi quyền hạn, không trả về SQL
                return {
                    "response": "Yêu cầu truy vấn thông tin của bạn không hợp lệ cho quyền học viên.",
                    "type": "query_response"
                }
        
        logger.info("Finished generating SQL for %s", request.role)
        logger.debug("SQL CODE:\n%s", str(sql_code))
        
        return {
            "sql_query": sql_code,
            "type": "sql_response"
        }
    
    @staticmethod
    async def generate_answer(request: AnswerGenerationRequest):
        """Bước 2: Chuyển kết quả truy vấn thành câu trả lời thân thiện"""

        try:
            chain = (
                PROMPT_SQL_ANSWER |
                ChatGroq(
                    model_name="openai/gpt-oss-20b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "chat_history": format_chat_history(request.chat_history),
                "question": request.message, 
                "result": request.sql_result
            })
        except Exception as e:
            logger.exception("Failed to generate SQL answer")
            raise InternalServerError(
                message=f"Failed to generate SQL answer: {str(e)}",
                type="generate_sql_answer_error"
            )
            
        logger.info("Finished generating SQL answer:\n%s", response)

        return {
            "response": response,
            "type": "query_response"
        }
