from langchain_core.prompts import PromptTemplate

# ==========================================
# CƠ SỞ LÝ THUYẾT: THANG ĐO NHẬN THỨC BLOOM
# ==========================================
BLOOM_TAXONOMY = {
    "easy": {
        "level": "Remember (Nhớ)",
        "instruction": "Tập trung vào việc ghi nhớ và nhận biết thông tin, sự kiện, thuật ngữ, khái niệm cơ bản. "
                       "Người học chỉ cần nhớ lại kiến thức. "
                       "Các từ khóa câu hỏi thường gặp: Ai, Cái gì, Ở đâu, Khi nào, Hãy định nghĩa, Hãy liệt kê."
    },
    "medium": {
        "level": "Understand (Hiểu)",
        "instruction": "Tập trung vào việc hiểu ý nghĩa, diễn dịch, tóm tắt hoặc suy diễn từ thông tin. "
                       "Người học phải giải thích được khái niệm bằng lời của mình hoặc nhận diện được ví dụ. "
                       "Các từ khóa câu hỏi thường gặp: Tại sao, Như thế nào, Hãy giải thích, Hãy so sánh, Hãy phân biệt."
    },
    "hard": {
        "level": "Apply (Vận dụng)",
        "instruction": "Tập trung vào việc sử dụng kiến thức, quy tắc, phương pháp vào các tình huống mới, cụ thể hoặc thực tế. "
                       "Người học phải giải quyết một vấn đề, tính toán hoặc dự đoán kết quả dựa trên kiến thức đã học. "
                       "Các từ khóa câu hỏi thường gặp: Vận dụng, Giải quyết, Tính toán, Dự đoán, Nếu [tình huống] xảy ra thì kết quả là gì?"
    }
}

# Prompt nay được thiết kế để chỉ tập trung vào 1 mức độ nhận thức (Cognitive Level) tại một thời điểm
BASE_INSTRUCTION = """
You are an expert educational instructional designer and precise assistant for generating high-quality multiple-choice quiz questions.

## Task
Generate {num_questions} quiz questions based strictly on the cognitive level defined below.

## Target Cognitive Level: {cognitive_level}
Instruction for this level: {level_instruction}

## Constraints:
1. Generate EXACTLY {num_questions} questions.
2. A question has exactly 4 options, and only 1 correct answer.
3. Provide a clear, logical explanation for why the answer is correct and why the others are wrong.
4. Rely strictly on the provided document content to generate questions.
5. Most of the provided document content will be related to programming, so make sure to correctly identify the programming language used in the document and use that language instead of randomly choosing languages like Python or Java.
6. You MUST respond strictly in JSON format.
"""

PROMPT_WITH_CONTENT = PromptTemplate.from_template(
    BASE_INSTRUCTION + """
## Document content to base questions on:
{document_content}

## Request Topic:
"{request}"

## Suggested format for your JSON response:
{{
    "questions": [
        {{
            "question_text": "...",
            "options": ["...", "...", "...", "..."],
            "correct_answer_index": 1,
            "explanation": "..."
            "cognitive_level": "{cognitive_level}"
        }}
    ]
}}
"""
)

PROMPT_WITHOUT_CONTENT = PromptTemplate.from_template(
    BASE_INSTRUCTION + """
## User Request Topic (Base your questions on your expert knowledge regarding this topic):
"{request}"

## Suggested format for your JSON response:
{{
    "questions": [
        {{
            "question_text": "...",
            "options": ["...", "...", "...", "..."],
            "correct_answer_index": 1,
            "explanation": "..."
            "cognitive_level": "{cognitive_level}"
        }}
    ]
}}
"""
)