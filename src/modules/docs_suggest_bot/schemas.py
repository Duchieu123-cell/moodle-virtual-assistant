from pydantic import BaseModel

class Question(BaseModel):
    question_content: str
    answers: list[str]

class Quiz(BaseModel):
    quiz_id: int
    quiz_name: str
    course_name: str
    questions: list[Question]
    type: str
    grade: float | None = None
    sumgrade: float | None = None

class Quizzes(BaseModel):
    quizzes_data: list[Quiz]