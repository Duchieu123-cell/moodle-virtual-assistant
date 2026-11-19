<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_teacher_courses extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            // Không cần tham số nào cho chức năng này
        ]);
    }
    /**
     * Lấy danh sách khóa học mà user hiện tại đang là giảng viên
     */
    public static function execute() {
        global $DB, $USER;
        // Lấy tất cả khóa học user đang enroll
        $enrolled_courses = enrol_get_users_courses($USER->id, true);
        $teacher_courses = [];

        foreach ($enrolled_courses as $course) {
            $context = \context_course::instance($course->id);
            
            // Kiểm tra xem người dùng có quyền xem điểm của tất cả mọi người hoặc quyền sửa khóa học không
            // Đây là 2 quyền đặc trưng nhất của Role Teacher/Editing Teacher
            if (has_capability('moodle/grade:viewall', $context) || has_capability('moodle/course:update', $context)) {
                $teacher_courses[] = [
                    'id'       => $course->id,
                    'fullname' => $course->fullname
                ];
            }
        }

        return [
            'courses' => $teacher_courses
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'courses' => new external_multiple_structure(
                new external_single_structure([
                    'id'       => new external_value(PARAM_INT, 'ID khóa học'),
                    'fullname' => new external_value(PARAM_RAW, 'Tên khóa học'),
                ])
            )
        ]);
    }
}