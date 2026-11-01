from pydantic import BaseModel, computed_field

class Info(BaseModel):
    name: str
    status: str # điểm cao nhất/chưa làm/bỏ lỡ (chưa làm và hết hạn)

class AnalyzeStudentRequest(BaseModel):
    student_name: str
    course_name: str
    quizzes: list[Info]
    assignments: list[Info]
    
    # Tự động phân loại môn học
    @computed_field
    def course_type(self) -> str:
        keywords = ["lab", "thực hành", "thí nghiệm"]
        name_lower = self.course_name.lower()
        
        # Kiểm tra xem có từ khóa nào xuất hiện trong tên môn không
        if any(kw in name_lower for kw in keywords):
            return "Thực hành / Thí nghiệm (Thiên về kỹ năng thao tác, công cụ, code, thực tế)"
        return "Lý thuyết (Thiên về khái niệm, tư duy, phương pháp luận)"


class Stats(BaseModel):
    total_students: int
    good: int
    average: int
    poor: int
    good_percent: float
    average_percent: float
    poor_percent: float
    
class Student(BaseModel):
    fullname: str
    course_completion_percentage: float

class AnalyzeCourseRequest(BaseModel):
    course_name: str
    statistics: Stats
    top_performing: list[Student]
    at_risk: list[Student]