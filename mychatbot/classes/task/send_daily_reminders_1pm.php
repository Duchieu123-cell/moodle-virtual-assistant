<?php
namespace local_mychatbot\task;

defined('MOODLE_INTERNAL') || die();

use core_user;

class send_daily_reminders_1pm extends \core\task\scheduled_task {
    public function get_name() {
        return get_string('task_send_daily_reminders_1pm', 'local_mychatbot');
    }

    public function execute() {
        global $DB, $CFG;
        $origin_url = $CFG->wwwroot;
        mtrace("Task started: Send Daily Chatbot Reminders for 13:00 group...");
        // Lấy URL FastAPI từ cài đặt
        $fastapi_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($fastapi_url)) {
            mtrace("Lỗi: FastAPI URL chưa được cấu hình.");
            return;
        }
        $reminder_endpoint = $fastapi_url . '/daily_reminders_batch';

        // Lấy tất cả người dùng (u) MÀ:
        // 1. Đã đăng ký nhận (r.registered = 1)
        // 2. Không bị xóa (u.deleted = 0)
        // 3. Không bị treo (u.suspended = 0)
        // 4. Không chặn email (u.emailstop = 0)
        $sql = "SELECT u.*
                FROM {user} AS u
                JOIN {local_mychatbot_daily_reminder_register} AS r ON u.id = r.userid
                WHERE r.registered = 1
                AND r.remindertime = 13
                AND u.deleted = 0
                AND u.suspended = 0
                AND u.emailstop = 0";

        // === TỐI ƯU BỘ NHỚ ===
        // Dùng get_recordset_sql thay vì get_records_sql
        // Recordset không tải hàng ngàn user vào bộ nhớ cùng lúc
        $recordset = $DB->get_recordset_sql($sql);

        if (!$recordset->valid()) {
            mtrace("No users registered for 13:00 group. Task finished.");
            $recordset->close();
            return;
        }

        // === LOGIC BATCHING (GOM LÔ) ===
        $chunksize = 50; // Xử lý 50 user mỗi lệnh gọi API
        $userchunk = []; // Mảng chứa lô hiện tại

        foreach ($recordset as $user) {
            $userchunk[$user->id] = $user; // Lưu user object, dùng ID làm key
            // Nếu lô đã đủ 50 user
            if (count($userchunk) >= $chunksize) {
                mtrace("Processing chunk of " . count($userchunk) . " users...");
                // Gửi lô này đi xử lý (gọi API và gửi mail)
                $this->process_reminder_chunk($userchunk, $reminder_endpoint, $origin_url);
                // Xóa lô để bắt đầu lại
                $userchunk = [];
            }
        }
        // Xử lý phần lẻ còn lại (ví dụ: còn 15 user cuối)
        if (!empty($userchunk)) {
            mtrace("Processing final chunk of " . count($userchunk) . " users...");
            $this->process_reminder_chunk($userchunk, $reminder_endpoint, $origin_url);
        }
        
        $recordset->close(); // Đóng recordset
        mtrace("Task finished for 13:00 group.");
    }
    /**
     * Xử lý một lô user, gọi API 1 lần
     * @param array $userchunk Mảng các user object [userid => userobj]
     * @param string $reminder_endpoint URL của API batch
     * @param string $origin_url URL gốc của Moodle
     */
    private function process_reminder_chunk(array $userchunk, $reminder_endpoint, $origin_url) {
        global $DB;
        // 1. Chuẩn bị dữ liệu gửi cho chatbot backend FastAPI
        $users_data_for_api = [];
        
        $sql_1 = "SELECT DISTINCT c.id AS course_id, c.fullname AS course_name
                    FROM {user_enrolments} AS ue
                    JOIN {enrol} AS e ON ue.enrolid = e.id
                    JOIN {course} AS c ON e.courseid = c.id
                    WHERE ue.userid = ?
                    AND ue.status = 0
                    AND (ue.timeend = 0 OR ue.timeend > UNIX_TIMESTAMP())
                    AND e.status = 0";
        $sql_2 = "SELECT COUNT(q.id)
                    FROM {quiz} AS q
                    JOIN {course_modules} AS cm ON q.id = cm.instance AND cm.course = q.course
                    JOIN {modules} AS m ON cm.module = m.id
                    WHERE q.course = ?
                    AND m.name = 'quiz'
                    AND cm.visible = 1
                    AND cm.deletioninprogress = 0";
        $sql_3 = "SELECT COUNT(a.id)
                    FROM {assign} AS a
                    JOIN {course_modules} AS cm ON a.id = cm.instance AND cm.course = a.course
                    JOIN {modules} AS m ON cm.module = m.id
                    WHERE a.course = ?
                    AND m.name = 'assign'
                    AND cm.visible = 1
                    AND cm.deletioninprogress = 0";
        $sql_4 = "SELECT COUNT(q.id)
                    FROM {quiz} AS q
                    JOIN {course_modules} AS cm ON q.id = cm.instance AND cm.course = q.course
                    JOIN {modules} AS m ON cm.module = m.id
                    WHERE q.course = ?
                    AND m.name = 'quiz'
                    AND cm.visible = 1
                    AND cm.deletioninprogress = 0
                    AND (
                        (NOT EXISTS (SELECT 1 FROM {quiz_attempts} AS qa WHERE qa.quiz = q.id AND qa.userid = ?)) OR
                        (EXISTS (SELECT 1 FROM {quiz_attempts} AS qa WHERE qa.quiz = q.id AND qa.userid = ? AND qa.state != 'finished'))
                    )";
        $sql_5 = "SELECT COUNT(a.id)
                    FROM {assign} AS a
                    JOIN {course_modules} AS cm ON a.id = cm.instance AND cm.course = a.course
                    JOIN {modules} AS m ON cm.module = m.id
                    WHERE a.course = ?
                    AND m.name = 'assign'
                    AND cm.visible = 1
                    AND cm.deletioninprogress = 0
                    AND (
                        (NOT EXISTS (SELECT 1 FROM {assign_submission} AS asub WHERE asub.assignment = a.id AND asub.userid = ?)) OR
                        (EXISTS (SELECT 1 FROM {assign_submission} AS asub WHERE asub.assignment = a.id AND asub.userid = ? AND asub.status != 'submitted'))
                    )";
        foreach ($userchunk as $user) {
            $courses_recordset = $DB->get_recordset_sql($sql_1, [$user->id]);

            if (!$courses_recordset->valid()) {
                // Người dùng không có khóa học nào, bỏ qua người dùng này
                $courses_recordset->close();
                continue;
            }

            $reminder_data = [];
            foreach ($courses_recordset as $course) {
                $total_quizzes_of_course = $DB->count_records_sql($sql_2, [$course->course_id]);
                $total_assignments_of_course = $DB->count_records_sql($sql_3, [$course->course_id]);
                $unfinished_quizzes_of_course = $DB->count_records_sql($sql_4, [$course->course_id, $user->id, $user->id]);
                $not_submitted_assignments_of_course = $DB->count_records_sql($sql_5, [$course->course_id, $user->id, $user->id]);
                $reminder_data[] = [
                    'course_id'                           => $course->course_id,
                    'course_name'                         => $course->course_name,
                    'total_quizzes_of_course'             => $total_quizzes_of_course,
                    'total_assignments_of_course'         => $total_assignments_of_course,
                    'unfinished_quizzes_of_course'        => $unfinished_quizzes_of_course,
                    'not_submitted_assignments_of_course' => $not_submitted_assignments_of_course
                ];
            }
            $courses_recordset->close();
            if (empty($reminder_data)) {
                continue; // Bỏ qua nếu không có dữ liệu nhắc nhở
            }
            $users_data_for_api[] = [
                'user_id'       => $user->id,
                'user_fullname' => fullname($user),
                'reminder_data' => $reminder_data
            ];
        }

        try {
            // 2. Thực hiện MỘT lệnh cURL cho cả lô
            $postdata = json_encode(['users' => $users_data_for_api]); // Gửi 1 mảng user
            $ch = curl_init();
            curl_setopt($ch, CURLOPT_URL, $reminder_endpoint);
            curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            curl_setopt($ch, CURLOPT_POST, 1);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $postdata);
            curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
            curl_setopt($ch, CURLOPT_TIMEOUT, 60);
            $raw_response = curl_exec($ch);
            $httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $curl_error = curl_error($ch);
            curl_close($ch);

            if ($raw_response === false || $httpcode !== 200) {
                mtrace("cURL Error (batch): " . $curl_error);
                return;
            }
            $data = json_decode($raw_response);

            // Giả sử FastAPI trả về: {"results": [{"user_id": 123, "response": "..."}, ...]}
            if (empty($data->results) || !is_array($data->results)) {
                mtrace("Lỗi API: Dữ liệu trả về không phải mảng 'results'");
                return;
            }

            // 3. Loop qua PHẢN HỒI (nhanh, trong bộ nhớ) và gửi mail
            foreach ($data->results as $result) {
                if (empty($result->user_id) || empty($result->response)) {
                    continue; // Bỏ qua nếu dữ liệu lỗi
                }

                $userid = $result->user_id;
                
                // Lấy lại user object từ mảng $userchunk ban đầu
                if (!isset($userchunk[$userid])) {
                    mtrace("Lỗi Logic: API trả về userid không có trong lô");
                    continue;
                }
                $user = $userchunk[$userid];

                // 4. Phân tích Markdown sang HTML
                $html_message = $this->parse_markdown_to_html($result->response, $origin_url);

                // 5. GỌI message_send() (Nhanh)
                // Moodle sẽ tự động dùng SMTP (Gmail) nếu admin đã cấu hình
                $message = new \core\message\message();
                $message->component = 'local_mychatbot';
                $message->name = 'daily_reminder';
                $message->userfrom = core_user::get_noreply_user();
                $message->userto = $user;
                $message->subject = get_string('dailyremindersubject', 'local_mychatbot');
                $message->fullmessage = $html_message;
                $message->fullmessageformat = FORMAT_HTML;
                $message->notification = 1;
                
                if (message_send($message)) {
                    mtrace("Queued email for user: " . fullname($user));
                } else {
                    mtrace("Failed to queue email for user: " . fullname($user));
                }
            }

        } catch (\Exception $e) {
            mtrace("Lỗi (batch): " . $e->getMessage());
        }
    }
    /**
     * Hàm trợ giúp chuyển đổi Markdown link sang HTML
     * @param string $text Nội dung thô từ bot
     * @param string $origin_url URL gốc của Moodle
     */
    private function parse_markdown_to_html($text, $origin_url) {
        // 1. (Bảo mật) Thoát các HTML đặc biệt để tránh XSS
        $text = htmlspecialchars($text, ENT_QUOTES, 'UTF-8');
        // 2. Chuyển đổi [text](url)
        $text = preg_replace_callback(
            '/\[([^\]]+)\]\(([^)]+)\)/', // Regex: [text](url)
            function($matches) use ($origin_url) {
                $link_text = $matches[1];
                $url = $matches[2];
                $url = $origin_url . $url;
                mtrace("Last URL: " . $url);
                return '<a href="' . $url . '">' . $link_text . '</a>';
            },
            $text
        );
        
        // 3. Chuyển đổi xuống dòng (newline) thành <br>
        $text = nl2br($text);
        
        return $text;
    }
}