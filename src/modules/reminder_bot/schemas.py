from pydantic import BaseModel


class AssignmentData(BaseModel):
    assignment_id: int
    assignment_name: str
    assignment_duedate: int 
    assignment_allowsubmissionsfromdate: int
    course_module_id: int

class AssignmentReminderItem(BaseModel):
    course_name: str
    assignments_pending: list[AssignmentData]
    
class AssignReminderRequestItem(BaseModel):
    user_id: int
    time_now: int
    reminder_data: list[AssignmentReminderItem]
    


# Quiz related models
class QuizData(BaseModel):
    quiz_id: int
    quiz_name: str
    quiz_timeclose: int
    quiz_timelimit: int
    course_module_id: int

class QuizReminderItem(BaseModel):
    course_name: str
    total_quizzes_of_course: int
    missed_quizzes_count: int
    quizzes: list[QuizData]

class QuizReminderRequestItem(BaseModel):
    user_id: int
    time_now: int
    arms_state: list[dict[str, int]]
    reminder_data: list[QuizReminderItem]