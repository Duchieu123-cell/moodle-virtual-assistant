from langchain_core.prompts import PromptTemplate

PROMPT_ANALYZE_COURSE_PROGRESS = PromptTemplate.from_template("""
You are a pedagogical Vietnamese assistant. Based on the following overall statistics and the list of high-performing and low-performing students, write a concise comment that encourages the instructor and suggests 1 or 2 specific actions they should take to support the low-performing students.

## Course name: {course_name}

## Overall statistics:
{overall_statistics}

## Instructions:
    1. Make sure the response in Vietnamese.
    2. Make sure your response is HTML-friendly for better readability.
    3. Use the provided statistics and student performance data to inform your comment and suggestions.

## Example format for your response:
<h6>
    (Tiêu đề ngắn gọn)
</h6>
<p>
    (Phân tích của bạn)
</p>
""")


PROMPT_ANALYZE_STUDENT_PROGRESS = PromptTemplate.from_template("""
Bạn là một trợ giảng xuất sắc. Hãy phân tích chi tiết tiến độ của học viên này và đưa ra các đề xuất cá nhân hóa cho giảng viên để hỗ trợ học viên.

## Thông tin môn học:
- Tên môn học: {course_name}
- Phân loại môn học: {course_type}

## Dữ liệu tiến độ của học viên:
{progress_data}

## Hướng dẫn (Yêu cầu tuân thủ nghiêm ngặt):
1. Phản hồi hoàn toàn bằng tiếng Việt.
2. Định dạng đầu ra bằng HTML (sử dụng <ul>, <li>, <strong>) để dễ đọc.
3. Cung cấp đúng 3 đến 4 đề xuất ngắn gọn, mang tính hành động.
4. CHIẾN LƯỢC ĐỀ XUẤT (Dựa trên "Phân loại môn học"):
   - Các đề xuất phải mang tính hành động và LIÊN QUAN CHẶT CHẼ đến đặc thù của môn học "{course_name}".
   - LƯU Ý QUAN TRỌNG: Nếu là môn "Thực hành / Thí nghiệm": Tập trung đề xuất cung cấp source code mẫu, video thao tác hướng dẫn (tutorial), môi trường test (sandbox), hoặc các lỗi phổ biến khi thực hành.
   - Nếu là môn "Lý thuyết": Tập trung đề xuất cung cấp tài liệu đọc thêm, sơ đồ tư duy (mindmap) hoặc các ví dụ case-study.

## Cấu trúc phản hồi:
<h6>
    (Tiêu đề ngắn gọn)
</h6>
<p>
    (Phân tích của bạn)
</p>
""")