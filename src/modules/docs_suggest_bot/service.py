from src.modules.docs_suggest_bot.prompt import (
    PROMPT_DOCS_SUGGEST_FOR_QUIZ, 
    PROMPT_DOCS_SUGGEST_FOR_LOW_GRADE_QUIZ
)
from src.modules.docs_suggest_bot.schemas import Quizzes
from src.modules.vector_database.vector_db import VectorDatabaseSingleton
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from src.core.config import settings
import json

GROQ_API_KEY = settings.GROQ_API_KEY

class DocsSuggestService():
    vector_db = VectorDatabaseSingleton.get()
    
    @staticmethod
    async def get_docs_suggestion(quiz, question_answers, docs_json):
        if quiz.type == "new":
            chain = (
                PROMPT_DOCS_SUGGEST_FOR_QUIZ |
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "quiz_name": quiz.quiz_name,
                "question_answers": question_answers,
                "docs_json": docs_json
            })
            return response
        elif quiz.type == "lowscore":
            chain = (
                PROMPT_DOCS_SUGGEST_FOR_LOW_GRADE_QUIZ |
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            response = await chain.ainvoke({
                "quiz_name": quiz.quiz_name,
                "question_answers": question_answers,
                "docs_json": docs_json,
                "grade": quiz.grade,
                "sumgrade": quiz.sumgrade
            })
            return response
    
    @staticmethod
    async def check_docs(request: Quizzes):
        docs_data = []
        for quiz in request.quizzes_data:
            question_answers = ""
            num_question = 1
            fileinfos_for_return = [] # cho kết quả trả về API cho quiz đang xét
            fileinfos_for_prompt = {} # cho kết quả đưa vào prompt AI cho quiz đang xét
            for question in quiz.questions:
                query = question.question_content + ' ' + ' '.join(question.answers)
                # Lấy kết quả tốt nhất sau khi đã Rerank cho từng câu hỏi
                retrieved_docs = await DocsSuggestService.vector_db.search_with_rerank(
                    query=query,
                    k_return=1,
                    k_search=10,
                    threshold=0.85,
                    metadata_filters={
                        "course_name": quiz.course_name
                    }
                )
                
                # fallback khi retrieved_docs is None hoặc len(retrieved_docs) == 0
                if not retrieved_docs or len(retrieved_docs) == 0:
                    print(f"LOG: No documents for question: {question.question_content}")
                    continue

                # Tạo chuỗi question_answers để đưa vào prompt AI
                question_answers += f"\nQuestion {num_question}: {question.question_content}\nAnswers: {', '.join(question.answers)}\n\n"
                num_question += 1
                for doc in retrieved_docs:
                    filename = doc.metadata.get('filename')
                    page = int(doc.metadata.get('page'))
                    fileurl = doc.metadata.get('fileurl')
                    
                    fileinfo_for_return = {
                        "filename"  : filename,
                        "fileurl"   : fileurl,
                        "pagenumber": page
                    }
                    if (fileinfo_for_return not in fileinfos_for_return):
                        fileinfos_for_return.append(fileinfo_for_return)

                    if filename not in fileinfos_for_prompt:
                        fileinfos_for_prompt[filename] = {}

                    page_number_as_key = f"page {page}"
                    if page_number_as_key not in fileinfos_for_prompt[filename]:
                        fileinfos_for_prompt[filename][page_number_as_key] = {}

                    chunk_number_as_key = f"chunk {int(doc.metadata.get('start_index'))}"
                    fileinfos_for_prompt[filename][page_number_as_key][chunk_number_as_key] = doc.page_content

            # Sau khi đã duyệt tất cả câu hỏi của quiz đang xét, gọi AI để lấy nội dung gợi ý cho quiz đó
            print("----- fileinfos_for_prompt -----")
            print(fileinfos_for_prompt)
            print("----- fileinfos_for_return -----")
            print(fileinfos_for_return)
            print('--------------------------------')
            fileinfos_for_prompt_json = json.dumps(fileinfos_for_prompt, indent=4)
            docs_suggestion = await DocsSuggestService.get_docs_suggestion(quiz, question_answers, fileinfos_for_prompt_json)
            docs_data.append({
                "quiz_id"  : quiz.quiz_id,
                "content"  : docs_suggestion,
                "fileinfos": fileinfos_for_return
            })
        
        return { "docs_data": docs_data }
        