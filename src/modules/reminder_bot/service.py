from src.modules.reminder_bot.prompt import (
    PROMPT_REMINDER_ASSIGNMENT,
    PROMPT_REMINDER_QUIZ
)
from src.modules.reminder_bot import (
    assign_format,
    quiz_format
)
from src.modules.reminder_bot.schemas import (
    AssignReminderRequestItem,
    QuizReminderRequestItem
)
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from datetime import datetime
from src.core.config import settings
from datetime import datetime, timedelta
import numpy as np
from src.core.exception import InternalServerError
import logging

GROQ_API_KEY = settings.GROQ_API_KEY
logger = logging.getLogger(__name__)

def convert_time_vn(time_str: str):
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    vn_time = dt.strftime("%H:%M %d/%m/%Y")
    return vn_time
    
class AssignReminderService():
    limit = 4
    
    @staticmethod
    async def create_assignment_reminder(list_assignments, time_now):
        full = []
        allowed_submission_assignments = []
        not_allowed_submission_assignments = []
        number_of_assignments_left = len(list_assignments)
        red, orange, white = False, False, False
        red_multiple = False
        submission_open, submission_not_open = False, False
        for a in list_assignments:
            duedate = convert_time_vn(str(datetime.fromtimestamp(a["assignment_duedate"])))
            if a["assignment_allowsubmissionsfromdate"] <= time_now:
                submission_open = True
                allowed_submission_assignments.append({
                    "content": f"- {a["assignment_name"]} của khóa {a["course_name"]} sẽ kết thúc vào {duedate}.",
                    "course_module_id": a["course_module_id"],
                    "severity_level": a["severity_level"]
                })
            else:
                submission_not_open = True
                not_allowed_submission_assignments.append({
                    "content": f"- {a["assignment_name"]} của khóa {a["course_name"]} sẽ mở nộp vào {convert_time_vn(str(datetime.fromtimestamp(a["assignment_allowsubmissionsfromdate"])))} và kết thúc vào {duedate}.",
                    "course_module_id": a["course_module_id"],
                    "severity_level": a["severity_level"]
                })
            if a["severity_level"] == 1:
                if red:
                    red_multiple = True
                red = True
                content = f'''
                    assignment_name: {a["assignment_name"]}
                    assignment_priority: {number_of_assignments_left}
                    assignment_deadline_at: {duedate}
                ''' 
                full.append(content)
                number_of_assignments_left -= 1
            elif a["severity_level"] == 0:
                orange = True
                if red:
                    continue
                else:
                    content = f'''
                        assignment_name: {a["assignment_name"]}
                        assignment_priority: {number_of_assignments_left}
                        assignment_deadline_at: {duedate}
                    ''' 
                    full.append(content)
                    number_of_assignments_left -= 1
            else:
                white = True
                if red or orange:
                    continue
                else:
                    content = f'''
                        assignment_name: {a["assignment_name"]}
                        assignment_priority: {number_of_assignments_left}
                        assignment_deadline_at: {duedate}
                    ''' 
                    full.append(content)
                    number_of_assignments_left -= 1
                

        if submission_open and submission_not_open:
            reminder_format = assign_format.reminder_format_1
        elif submission_open:
            reminder_format = assign_format.reminder_format_2
        else:
            reminder_format = assign_format.reminder_format_3
            
        if red:
            recommend_format = assign_format.recommend_format_1_1 if red_multiple else assign_format.recommend_format_1_2
        elif orange and white:
            recommend_format = assign_format.recommend_format_2
        elif orange:
            recommend_format = assign_format.recommend_format_3
        else:
            recommend_format = assign_format.recommend_format_4
            
        input = "\n".join(full)
        logger.debug("assignment reminder input:\n%s", input)
        
        try:
            chain = (
                PROMPT_REMINDER_ASSIGNMENT |
                ChatGroq(
                    model_name="qwen/qwen3.6-27b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            reminder = await chain.ainvoke({ 
                "input": input,
                "number_of_assignments": len(list_assignments),
                "reminder_format": reminder_format,
                "recommend_format": recommend_format
            })
            
        except Exception as e:
            raise InternalServerError(f"Lỗi xảy ra khi chatbot tạo nhắc nhở assignment: {str(e)}")
        
        logger.debug("Assignment reminder:\n%s", reminder)
        
        return {
            "response": reminder,
            "allowed_submission_assignments": allowed_submission_assignments,
            "not_allowed_submission_assignments": not_allowed_submission_assignments
        }
    
    
    @staticmethod
    async def check_assignment(request: AssignReminderRequestItem):
        assignments = []
        for course in request.reminder_data:
            logger.info("Processing Course: %s", course.course_name)
            
            for assignment in course.assignments_pending:
                assignment = {
                    "assignment_name": assignment.assignment_name,
                    "assignment_duedate": assignment.assignment_duedate,
                    "assignment_allowsubmissionsfromdate": assignment.assignment_allowsubmissionsfromdate,
                    "course_name": course.course_name,
                    "course_module_id": assignment.course_module_id,
                }
                
                assignments.append(assignment)
                
            logger.info("Done processing course: %s, total assignments found: %d", course.course_name, len(course.assignments_pending))

        if len(assignments) == 0:
            logger.info("User %d has no assignments available", request.user_id)
            return "No assignments available.", [], []

        assignments.sort(key=lambda a: (a["assignment_duedate"], a["assignment_allowsubmissionsfromdate"]))
        reminders = []
        for a in assignments:
            if len(reminders) >= AssignReminderService.limit:
                break
            
            time_left_sec = max(a["assignment_duedate"] - request.time_now, 0)
            time_left_hours = time_left_sec / 3600.0
            if time_left_hours <= 7*24:
                a["severity_level"] = 1
            elif time_left_hours <= 14*24:
                a["severity_level"] = 0
            else:
                a["severity_level"] = -1
            reminders.append(a)

        reminder_data = await AssignReminderService.create_assignment_reminder(reminders, request.time_now)
        return reminder_data
    

class QuizReminderService():
    limit = 4
    SMOOTH = 1.0
    red_urgent_threshold = 8 # 8 giờ
    orange_urgent_threshold = 16 # 16 giờ
    
    # Định nghĩa 5 "Arms" (chiến lược)
    STRATEGIES = {
        1: {"w_time": 0.8, "w_missed": 0.2}, # Ưu tiên Thời gian alpha, beta
        2: {"w_time": 0.7, "w_missed": 0.3}, # Hơi ưu tiên Thời gian
        3: {"w_time": 0.5, "w_missed": 0.5}, # Cân bằng
        4: {"w_time": 0.3, "w_missed": 0.7}, # Hơi ưu tiên Thói quen (trường hợp bỏ lỡ quiz)
        5: {"w_time": 0.2, "w_missed": 0.8}, # Ưu tiên Thói quen
    }
    
    @staticmethod
    def find_next_slot(start_search_ts, time_close_ts, time_limit_sec):
        """
        Helper: Tìm "khe" (slot) làm bài thân thiện (8h-22h) đầu tiên
        SAU thời điểm start_search_ts.
        """
        # --- Các hằng số (có thể điều chỉnh) ---
        # Vùng đệm an toàn: Đề xuất phải trước deadline ít nhất (thời gian làm + 1 giờ đệm).
        # Nếu quiz 60 phút (3600s), đệm 1h (3600s) -> 7200s
        MIN_SAFETY_BUFFER_SEC = 3600  # Đệm ít nhất 1 giờ
        # Khung giờ "thức" (Human-friendly)
        WAKE_HOUR = 8    # 8:00 Sáng
        SLEEP_HOUR = 22   # 10:00 Tối
        
        # 1. Tính thời điểm bắt đầu an toàn cuối cùng
        # lsst_ts = Thời điểm muộn nhất có thể BẮT ĐẦU làm quiz
        lsst_ts = time_close_ts - time_limit_sec - MIN_SAFETY_BUFFER_SEC
        
        # 2. Bắt đầu tìm kiếm từ thời điểm 'start_search_ts'
        current_dt = datetime.fromtimestamp(start_search_ts)
        current_hour = current_dt.hour
        
        # 3. Điều chỉnh 'suggested_dt' đến giờ "thức" gần nhất
        if current_hour < WAKE_HOUR:
            # Nếu đang là 3h sáng -> đẩy lên 8h sáng
            suggested_dt = current_dt.replace(hour=WAKE_HOUR, minute=0, second=0)
        elif current_hour >= SLEEP_HOUR:
            # Nếu đang là 10h tối -> đẩy lên 8h sáng hôm sau
            suggested_dt = (current_dt + timedelta(days=1)).replace(hour=WAKE_HOUR, minute=0, second=0)
        else:
            # Đang trong giờ "thức" (ví dụ 14:30)
            # -> Làm tròn lên giờ tiếp theo cho đẹp (15:00)
            suggested_dt = (current_dt + timedelta(hours=1)).replace(minute=0, second=0)

        # 4. Kiểm tra an toàn
        # Nếu thời điểm đề xuất (sau khi điều chỉnh) đã vượt quá 
        # thời điểm an toàn cuối cùng -> không đề xuất được
        if suggested_dt.timestamp() > lsst_ts:
            return None
            
        return suggested_dt

    @staticmethod
    def suggest_schedule_for_white_quizzes(white_quizzes_sorted, time_now):
        """
        Hàm xếp lịch đề xuất cho các quiz "mức độ bình thường" (white alert).
        Ý tưởng:
        1. Sắp xếp theo priority (đã làm ở ngoài)
        2. Tuần tự gán lịch để không trùng lặp
        """
        suggestions_map = {}
        # Đây là biến "theo dõi" lịch: "Lịch của bạn đang bận đến mấy giờ?"
        # Ban đầu, nó trống (tính từ 16 giờ tới)
        next_available_slot_ts = time_now + 16*3600
        
        # "Nghỉ giải lao" giữa các quiz
        BREAK_TIME_SEC = 900  # 15 phút

        # white_quizzes_sorted đã được sắp xếp theo priority
        for quiz in white_quizzes_sorted:
            
            # Tìm khe hợp lý TIẾP THEO (sau khi lịch bận)
            suggested_dt = QuizReminderService.find_next_slot(
                next_available_slot_ts,
                quiz['quiz_time_close'],
                quiz['quiz_time_limit']
            )
            
            if suggested_dt:
                # Nếu tìm thấy một khe
                suggestions_map[quiz['quiz_id']] = suggested_dt.timestamp()
                
                # CẬP NHẬT LỊCH: Lịch sẽ bận cho đến khi
                # quiz này kết thúc + thời gian nghỉ
                slot_end_ts = suggested_dt.timestamp() + quiz['quiz_time_limit']
                next_available_slot_ts = slot_end_ts + BREAK_TIME_SEC
            else:
                # Nếu không tìm thấy khe nào hợp lý (quiz quá sát)
                suggestions_map[quiz['quiz_id']] = None
        
        return suggestions_map
    
    @staticmethod
    async def create_quiz_reminder(list_quizzes, time_now):
        full, formatted_quizzes = [], []
        white_quizzes, suggestion_list = [], []
        suggestion_title = ""
        num = len(list_quizzes)
        red, orange, white = False, False, False
        red_mul, orange_mul, white_mul = False, False, False
        for q in list_quizzes:
            if num % 2 == 0:
                content = f"- {q['quiz_name']} của khóa {q['course_name']} sẽ kết thúc vào {convert_time_vn(str(datetime.fromtimestamp(q['quiz_time_close'])))}."
            else:
                content = f"- {q['quiz_name']} thuộc khóa {q['course_name']} sẽ đóng lúc {convert_time_vn(str(datetime.fromtimestamp(q['quiz_time_close'])))}."
            
            formatted_quizzes.append({
                "content"         : content,
                "course_module_id": q["course_module_id"],
                "severity_level"  : q["severity_level"]
            })
            
            if q["severity_level"] == 1:
                if red:
                    red_mul = True
                red = True
                full.append(f'''
                    quiz_name: {q["quiz_name"]}
                    quiz_priority: {num}
                ''')
                num -= 1
            elif q["severity_level"] == 0:
                if orange:
                    orange_mul = True
                orange = True
                if red:
                    continue
                else:
                    full.append(f'''
                        quiz_name: {q["quiz_name"]}
                        quiz_priority: {num}
                    ''')
                    num -= 1
            else:
                if white:
                    white_mul = True
                white = True
                white_quizzes.append(q)
                if red or orange:
                    continue
                else:
                    full.append(f'''
                        quiz_name: {q["quiz_name"]}
                        quiz_priority: {num}
                    ''')
                    num -= 1
                    
        if len(white_quizzes) != 0:
            suggestions_map = QuizReminderService.suggest_schedule_for_white_quizzes(white_quizzes, time_now)
            if len(white_quizzes) == 1 and suggestions_map.get(white_quizzes[0]["quiz_id"]) != None:
                if red or orange:
                    suggestion_title = f"Ưu tiên hoàn thành các quiz khẩn cấp. Đối với quiz chưa khẩn cấp, bạn có thể tham khảo thời gian đề xuất:"
                else:
                    suggestion_title = f"Thời gian đề xuất cho bạn thực hiện quiz:"
                
                suggestion_list.append({
                    "quiz_id"         : white_quizzes[0]['quiz_id'],
                    "quiz_name"       : white_quizzes[0]['quiz_name'],
                    "course_name"     : white_quizzes[0]['course_name'],
                    "course_module_id": white_quizzes[0]['course_module_id'],
                    "suggested_time"  : suggestions_map.get(white_quizzes[0]['quiz_id'])
                })
            elif len(white_quizzes) > 1:
                for q in white_quizzes:
                    suggested_dt = suggestions_map.get(q['quiz_id'])
                    if suggested_dt:
                        suggestion_list.append({
                            "quiz_id"         : q['quiz_id'],
                            "quiz_name"       : q['quiz_name'],
                            "course_name"     : q['course_name'],
                            "course_module_id": q['course_module_id'],
                            "suggested_time"  : suggested_dt
                        })

                if len(suggestion_list) != 0:
                    if red or orange:
                        suggestion_title = "Với các quiz chưa khẩn cấp, mình đề xuất các khung giờ:"
                    else:
                        suggestion_title = "Một số thời gian đề xuất cho bạn thực hiện:"
                        
        logger.debug("Selected quizzes for reminder: %s", suggestion_list)
        
        if red:
            if red_mul:
                reminder_format = quiz_format.reminder_format_5_1
                recommend_format = quiz_format.recommend_format_5_1
            else:
                reminder_format = quiz_format.reminder_format_5_2
                recommend_format = quiz_format.recommend_format_5_2
        elif orange and white:
            if not orange_mul:
                reminder_format = quiz_format.reminder_format_6_1
                recommend_format = quiz_format.recommend_format_6_1
            else:
                reminder_format = quiz_format.reminder_format_6_2
                recommend_format = quiz_format.recommend_format_6_2
        elif orange:
            reminder_format = quiz_format.reminder_format_7_1 if orange_mul else quiz_format.reminder_format_7_2
            recommend_format = quiz_format.recommend_format_7 if orange_mul else ""
        else:
            reminder_format = quiz_format.reminder_format_8_1 if white_mul else quiz_format.reminder_format_8_2
            recommend_format = quiz_format.recommend_format_8 if white_mul else ""
            
        input = "\n".join(full)
        logger.debug("input:\n%s", input)
        
        try:
            chain = (
                PROMPT_REMINDER_QUIZ |
                ChatGroq(
                    model_name="openai/gpt-oss-120b",
                    temperature=0,
                    groq_api_key=GROQ_API_KEY
                ) |
                StrOutputParser()
            )
            reminder = await chain.ainvoke({
                "input": input,
                "number_of_quizzes": len(list_quizzes), 
                "reminder_format": reminder_format,
                "recommend_format": recommend_format
            })
            
        except Exception as e:
            raise InternalServerError(f"Lỗi xảy ra khi chatbot tạo nhắc nhở quiz: {str(e)}")
        
        logger.debug("Quiz reminder:\n%s", reminder)
        
        if red:
            doc_needed_quizid = list_quizzes[0]['quiz_id']
        else:
            doc_needed_quizid = 0

        return {
            "response"         : reminder,
            "formatted_quizzes": formatted_quizzes,
            "suggestion_title" : suggestion_title,
            "suggestion_list"  : suggestion_list,
            "doc_needed_quizid": doc_needed_quizid
        }
    
    # -----------------------------------------------------------------
    # CHỌN CHIẾN LƯỢC TỐT NHẤT (THOMPSON SAMPLING)
    # -----------------------------------------------------------------
    @staticmethod
    def choose_best_arm(arms_state):
        """
        Chọn Arm tốt nhất cho user dựa trên Thompson Sampling.
        """
        best_arm_id = -1
        max_sample_value = -1

        chosen_strategy = None
        for arm in arms_state:
            # Lấy mẫu từ phân phối Beta(alpha, beta)
            sample = np.random.beta(arm['alpha'], arm['beta'])
            
            if sample > max_sample_value:
                max_sample_value = sample
                best_arm_id = arm['armid']
        
        # Lấy chiến lược (w_time, w_missed) tương ứng
        # (Nếu best_arm_id = -1, dùng Arm 3 - Cân bằng làm mặc định)
        if best_arm_id == -1:
            best_arm_id = 3 
            
        chosen_strategy = QuizReminderService.STRATEGIES[best_arm_id]
                
        return best_arm_id, chosen_strategy
    
    @staticmethod
    def compute_quiz_priority(time_close, missed_count, total_quizzes, time_now, w_time, w_missed):
        time_left_sec = max(time_close - time_now, 0)
        time_left_hours = time_left_sec / 3600.0
        max_time_window_hours = 72.0

        t = min(time_left_hours, max_time_window_hours)
        time_urgency = 1.0 - (t / max_time_window_hours)

        s = QuizReminderService.SMOOTH
        missed_score = (missed_count + s) / (total_quizzes + 2*s)
        missed_score = max(0.0, min(1.0, missed_score))

        bonus = 0.0
        severity_level = -1 # white alert (normal)
        if time_left_hours <= QuizReminderService.red_urgent_threshold:
            bonus = 0.15
            severity_level = 1 # red alert (high)
        elif time_left_hours <= QuizReminderService.orange_urgent_threshold:
            bonus = 0.10
            severity_level = 0 # orange alert (medium)

        score = w_time * time_urgency + w_missed * missed_score + bonus
        return score, severity_level
 
    @staticmethod
    async def check_quiz(request: QuizReminderRequestItem):
        # === BƯỚC 1: CHỌN CHIẾN LƯỢC (ARM) ===
        chosen_arm_id, chosen_strategy = QuizReminderService.choose_best_arm(request.arms_state)
        logger.info("User %d: Chosen Arm ID: %d, Strategy: %s", request.user_id, chosen_arm_id, chosen_strategy)

        # === BƯỚC 2: TÍNH TOÁN QUIZ ===
        quizzes = []
        for course in request.reminder_data:
            logger.info("Processing Course: %s", course.course_name)
            
            for quiz in course.quizzes:
                quiz_priority, severity_level = QuizReminderService.compute_quiz_priority(
                    quiz.quiz_timeclose,
                    course.total_quizzes_of_course, 
                    course.missed_quizzes_count,
                    request.time_now,
                    chosen_strategy["w_time"],
                    chosen_strategy["w_missed"]
                )
                quizzes.append({
                    "quiz_id"         : quiz.quiz_id,
                    "quiz_name"       : quiz.quiz_name,
                    "quiz_time_close" : quiz.quiz_timeclose,
                    "quiz_time_limit" : quiz.quiz_timelimit,
                    "quiz_priority"   : quiz_priority,
                    "severity_level"  : severity_level,
                    "course_name"     : course.course_name,
                    "course_module_id": quiz.course_module_id
                })

        if len(quizzes) == 0:
            logger.info("User %d has no quizzes available", request.user_id)
            return {
                "response"            : "No quizzes available.",
                "formatted_quizzes"   : [],
                "suggestion_title"    : '',
                "suggestion_list"     : [],
                "doc_suggest_for_quiz": 0,
                "reminded_quizzes"    : []
            }

        # === BƯỚC 3: SẮP XẾP VÀ LỌC (ĐƠN GIẢN HÓA) ===
        quizzes.sort(key=lambda q: (-q["quiz_priority"], q["quiz_time_close"]))
        reminders = []
        for q in quizzes:
            if len(reminders) >= QuizReminderService.limit:
                break
            reminders.append(q)

        # === BƯỚC 4: GHI LOG CHO MOODLE OBSERVER ===
        reminded_quizzes = []
        for q in reminders:
            reminded_quizzes.append({
                "quiz_id": q["quiz_id"],
                "arm_id": chosen_arm_id
            })

        # === BƯỚC 5: TẠO LỜI NHẮC ===
        reminder_data = await QuizReminderService.create_quiz_reminder(reminders, request.time_now)
        reminder_data["reminded_quizzes"] = reminded_quizzes
        return reminder_data