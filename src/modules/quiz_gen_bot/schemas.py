from pydantic import BaseModel, Field

class Question(BaseModel):
    """A single quiz question with options and the correct answer."""
    question_text: str = Field(..., description="Nội dung câu hỏi trắc nghiệm")
    options: list[str] = Field(..., description="Danh sách 4 đáp án (A, B, C, D)")
    correct_answer_index: int = Field(..., description="Vị trí index (0-3) của đáp án đúng trong list options")
    explanation: str = Field(..., description="Giải thích chi tiết tại sao đáp án này đúng theo logic")
    cognitive_level: str = Field(..., description="Mức độ nhận thức (Remember, Understand, hoặc Apply)")

class GeneratedQuiz(BaseModel):
    """A generated quiz with a list of questions."""
    questions: list[Question] | None = Field(default=None, description="List of quiz questions")