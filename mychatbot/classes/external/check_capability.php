<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class check_capability extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            // Không cần tham số nào cho chức năng này
        ]);
    }
    /**
     * Kiểm tra quyền của người dùng (là học viên trong ít nhất 1 khóa học hay không, giảng viên trong ít nhất 1 khóa học hay không)
     * Một người dùng có thể là student, teacher hoặc cả 2
     */
    public static function execute() {
        global $DB, $USER;
        // Lấy tất cả khóa học user đang enroll
        $enrolled_courses = enrol_get_users_courses($USER->id, true);
        $student = false;
        $teacher = false;

        foreach ($enrolled_courses as $course) {
            $context = \context_course::instance($course->id);
            
            // Kiểm tra xem người dùng có quyền xem điểm của tất cả mọi người hoặc quyền sửa khóa học không
            // Đây là 2 quyền đặc trưng nhất của Role Teacher/Editing Teacher
            if (has_capability('moodle/grade:viewall', $context) || has_capability('moodle/course:update', $context)) {
                $teacher = true;
            } else {
                $student = true;
            }
        }

        return [
            'student' => $student,
            'teacher' => $teacher
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'student' => new external_value(PARAM_BOOL, 'Người dùng có phải là học viên không'),
            'teacher' => new external_value(PARAM_BOOL, 'Người dùng có phải là giảng viên không')
        ]);
    }
}