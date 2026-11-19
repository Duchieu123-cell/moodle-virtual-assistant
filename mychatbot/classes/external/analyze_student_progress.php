<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class analyze_student_progress extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'ID khóa học'),
            'userid'   => new external_value(PARAM_INT, 'ID học viên')
        ]);
    }
    /**
     * Xử lý truy vấn dữ liệu học viên và gọi FastAPI để lấy nhận xét về tiến độ khóa học dựa trên courseid được chọn
     */
    public static function execute($courseid, $userid) {
        global $DB;
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }
        $time = time();

        // Kiểm tra quyền hạn (Giảng viên)
        $context = \context_course::instance($courseid);
        if (!has_capability('moodle/grade:viewall', $context) && !has_capability('moodle/course:update', $context)) {
            throw new \moodle_exception('nopermissions', 'error', '', 'Bạn không có quyền xem chi tiết trong khóa học này');
        }

        // Lấy tên học viên
        $student = $DB->get_record('user', array('id' => $userid), 'firstname, lastname');
        $student_fullname = $student->firstname . ' ' . $student->lastname;

        // 1. TRUY VẤN DỮ LIỆU QUIZ
        $quizzes = $DB->get_records('quiz', array('course' => $courseid), '', 'id, name, timeclose');
        $quiz_data = array();
        foreach ($quizzes as $q) {
            $grade = $DB->get_field('quiz_grades', 'grade', array('quiz' => $q->id, 'userid' => $userid));
            if ($grade !== false && !is_null($grade)) {
                $status = "Điểm: " . round($grade, 2);
            } else {
                $status = ($q->timeclose > 0 && $q->timeclose < $time) ? "Bỏ lỡ (Quá hạn)" : "Chưa thực hiện";
            }
            $quiz_data[] = array('name' => $q->name, 'status' => $status);
        }

        // 2. TRUY VẤN DỮ LIỆU ASSIGNMENT
        $assignments = $DB->get_records('assign', array('course' => $courseid), '', 'id, name, duedate');
        $assign_data = array();
        foreach ($assignments as $a) {
            // Kiểm tra điểm
            $grade = $DB->get_field('assign_grades', 'grade', array('assignment' => $a->id, 'userid' => $userid));
            // Kiểm tra trạng thái nộp bài
            $substatus = $DB->get_field('assign_submission', 'status', array('assignment' => $a->id, 'userid' => $userid, 'latest' => 1));

            if ($grade !== false && $grade >= 0) {
                $status = "Điểm: " . round($grade, 2);
            } elseif ($substatus === 'submitted') {
                $status = "Đã nộp (Chưa chấm)";
            } else {
                $status = ($a->duedate > 0 && $a->duedate < $time) ? "Bỏ lỡ (Quá hạn)" : "Chưa nộp bài";
            }
            $assign_data[] = array('name' => $a->name, 'status' => $status);
        }
        $course_name = $DB->get_field('course', 'fullname', array('id' => $courseid));
        // 3. GỌI API FASTAPI
        $payload = [
            'student_name' => $student_fullname,
            'course_name'  => $course_name,
            'quizzes'      => $quiz_data,
            'assignments'  => $assign_data
        ];
        $fastapi_url = $base_url . '/analyze/student';
        $ch = \curl_init();
        \curl_setopt($ch, CURLOPT_URL, $fastapi_url);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        \curl_setopt($ch, CURLOPT_POST, 1);
        \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        \curl_setopt($ch, CURLOPT_TIMEOUT, 30);

        $raw_response = \curl_exec($ch);
        $httpcode = \curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = \curl_error($ch);
        \curl_close($ch);
        if ($curl_error) {
            throw new \moodle_exception('cURL Error: ' . $curl_error);
        }
        if ($httpcode >= 400) {
            throw new \moodle_exception('API Error: ' . $httpcode . ' - ' . $raw_response);
        }
        $response_object = json_decode($raw_response);
        return [
            'response' => $response_object->response,
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'response' => new external_value(PARAM_RAW, 'Phản hồi từ FastAPI phân tích tiến độ học viên'),
        ]);
    }
}