from src.modules.quiz_gen_bot.prompt import (
    BLOOM_TAXONOMY, 
    PROMPT_WITH_CONTENT, 
    PROMPT_WITHOUT_CONTENT
)
from src.modules.quiz_gen_bot.schemas import GeneratedQuiz
from src.modules.file_processor.service import FileProcessService
from src.core.config import settings
from langchain_groq import ChatGroq
import asyncio
import os
from fastapi import HTTPException, status
import shutil
import uuid

GROQ_API_KEY = settings.GROQ_API_KEY 

class QuizGenService():

    @staticmethod
    async def _generate_for_level(context: str, request: str, num_questions: int, level_key: str):
        """
        Hàm private xử lý việc tạo câu hỏi cho một mức độ cụ thể.
        Giúp LLM tập trung hoàn toàn vào một logic duy nhất (Nhớ/Hiểu/Vận dụng).
        """
        if num_questions <= 0:
            return []

        level_info = BLOOM_TAXONOMY[level_key]
        
        # Khởi tạo mô hình
        llm = ChatGroq(
            model_name="openai/gpt-oss-120b",
            temperature=0.2,
            groq_api_key=GROQ_API_KEY
        ).with_structured_output(GeneratedQuiz, method="json_mode")

        try:
            if context:
                chain = PROMPT_WITH_CONTENT | llm
                response = await chain.ainvoke({
                    "document_content": context,
                    "request": request,
                    "num_questions": num_questions,
                    "cognitive_level": level_info["level"],
                    "level_instruction": level_info["instruction"]
                })
            else:
                chain = PROMPT_WITHOUT_CONTENT | llm
                response = await chain.ainvoke({
                    "request": request,
                    "num_questions": num_questions,
                    "cognitive_level": level_info["level"],
                    "level_instruction": level_info["instruction"]
                })
            
            if response and response.questions:
                return response.questions
            return []
            
        except Exception as e:
            print(f"Error generating {level_key} questions: {str(e)}")
            return []

    @staticmethod
    async def quiz_generate(context: str, request: str, num_easy: int, num_medium: int, num_hard: int):
        """
        Hàm chính tạo quiz: Sử dụng thuật toán chạy song song (Async) 
        để tổng hợp các câu hỏi từ 3 mức độ nhận thức khác nhau.
        """
        # 1. Tạo các tasks chạy song song để tối ưu tốc độ và tách biệt logic
        tasks = [
            QuizGenService._generate_for_level(context, request, num_easy, "easy"),
            QuizGenService._generate_for_level(context, request, num_medium, "medium"),
            QuizGenService._generate_for_level(context, request, num_hard, "hard")
        ]
        
        # 2. Đợi tất cả các luồng hoàn thành
        results = await asyncio.gather(*tasks)
        
        # 3. Gộp kết quả từ 3 luồng
        all_questions = []
        for q_list in results:
            print("-"*50)
            print(f"Generated {len(q_list)} questions for one level.")
            print(q_list)
            print("-"*50)
            all_questions.extend(q_list)
            
        # 4. Trả về format cuối cùng
        final_quiz = GeneratedQuiz(questions=all_questions)
        
        print(f"Generated {len(all_questions)} questions total.")
        return final_quiz.model_dump()
    
        # format kết quả cho ChatGroq.with_structured_output
        # return {
        #     "questions": [
        #         {
        #             "question_text": "Hàm nào dùng để in ra màn hình trong Python?",
        #             "options": ["echo", "print", "printf", "write"],
        #             "correct_answer_index": 1,
        #             "explanation": "Hàm print() là hàm tiêu chuẩn trong Python..."
        #         },
        #         {
        #             "question_text": "Để tạo một vòng lặp trong Python, bạn sử dụng từ khóa nào?",
        #             "options": ["loop", "for", "while", "repeat"],
        #             "correct_answer_index": 1,
        #             "explanation": "Từ khóa for được sử dụng để tạo vòng lặp trong Python..."
        #         },
        #         {
        #             "question_text": "Làm thế nào để khai báo một biến trong Python?",
        #             "options": ["var x = 10", "int x = 10", "x = 10", "declare x = 10"],
        #             "correct_answer_index": 2,
        #             "explanation": "Trong Python, bạn chỉ cần gán giá trị cho biến mà không cần khai báo kiểu dữ liệu..."
        #         },
        #         {
        #             "question_text": "Làm thế nào để định nghĩa một hàm trong Python?",
        #             "options": ["function myFunc():", "def myFunc():", "func myFunc():", "define myFunc():"],
        #             "correct_answer_index": 1,
        #             "explanation": "Từ khóa def được sử dụng để định nghĩa một hàm trong Python..."
        #         },
        #         {
        #             "question_text": "Làm thế nào để xử lý lỗi trong Python?",
        #             "options": ["try...catch", "try...except", "catch...try", "handle...error"],
        #             "correct_answer_index": 1,
        #             "explanation": "Cấu trúc try...except được sử dụng để xử lý lỗi trong Python..."
        #         }
        #     ]
        # }

    @staticmethod
    async def quiz_generate_process(prompt, num_easy, num_medium, num_hard, file):
        try:
            context = None
            if file:
                # 1. Lưu file tạm thời
                temp_dir = "files/file_quiz_gen"
                os.makedirs(temp_dir, exist_ok=True)
                unique_name = f"{uuid.uuid4()}_{file.filename}"
                temp_file_path = f"{temp_dir}/{unique_name}"
                
                with open(temp_file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                metadata = {
                    "filename": file.filename,
                    "mimetype": "application/pdf"
                }
                
                # 2. Xử lý file và trích xuất nội dung -> List[Document]
                docs = await FileProcessService.process_file(temp_file_path, metadata)
                
                # Xóa file tạm sau khi đã xử lý xong
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            
                # 3. Tạo ngữ cảnh (Context) có cấu trúc cho LLM
                context_parts = [f"--- File: {file.filename} ---"]
                for doc in docs:
                    page_info = doc.metadata.get('page', 'Unknown Page')
                    context_parts.append(f"--- Page {page_info} ---\n{doc.page_content}")
                
                context = "\n\n".join(context_parts)
                    
            response = await QuizGenService.quiz_generate(
                context, prompt, num_easy, num_medium, num_hard
            )
            # Kiểm tra kết quả
            if not response or not response.get("questions"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, 
                    detail="Mô hình không thể tạo ra câu hỏi từ nội dung/yêu cầu được cung cấp."
                )

            return response

        except HTTPException as http_ex:
            raise http_ex
        except Exception as e:
            print(f"Lỗi trong quá trình tạo quiz: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=f"Lỗi trong quá trình tạo quiz: {e}"
            )