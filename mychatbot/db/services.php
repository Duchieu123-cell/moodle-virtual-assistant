<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    // send_message
    'local_mychatbot_send_message' => [
        'classname'    => 'local_mychatbot\external\send_message',
        'description'  => 'Send a message to the chatbot.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use'
    ],
    'local_mychatbot_get_conversation_titles' => [
        'classname'    => '\local_mychatbot\external\get_conversation_titles',
        'description'  => 'Get all conversation titles for the user.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_conversation_history' => [
        'classname'    => '\local_mychatbot\external\get_conversation_history',
        'description'  => 'Get all messages for a specific conversation.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    // check_status
    'local_mychatbot_check_status' => [
        'classname'    => 'local_mychatbot\external\check_status',
        'description'  => 'Check chatbot backend status.',
        'type'         => 'read',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use'
    ],
    'local_mychatbot_get_quiz_reminder_history' => [
        'classname'    => '\local_mychatbot\external\get_quiz_reminder_history',
        'description'  => 'Get quiz reminders, triggering new pull if cooldown passed.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_assignment_reminder_history' => [
        'classname'    => '\local_mychatbot\external\get_assignment_reminder_history',
        'description'  => 'Get assignment reminders, triggering new pull if cooldown passed.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_add_calendar_quiz_event' => [
        'classname'    => '\local_mychatbot\external\add_calendar_quiz_event',
        'description'  => 'Add a quiz suggestion to the user calendar.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_replace_calendar_quiz_event' => [
        'classname'    => '\local_mychatbot\external\replace_calendar_quiz_event',
        'description'  => 'Replace a quiz suggestion in the user calendar.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_delete_calendar_quiz_event' => [
        'classname'    => '\local_mychatbot\external\delete_calendar_quiz_event',
        'description'  => 'Delete a quiz suggestion from the user calendar.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_current_quiz_suggestions' => [
        'classname'    => '\local_mychatbot\external\get_current_quiz_suggestions',
        'description'  => 'Get the latest quiz suggestions for the user.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_doc_needed_for_quiz' => [
        'classname'    => '\local_mychatbot\external\get_doc_needed_for_quiz',
        'description'  => 'Get the latest documents needed for the quiz for the user.',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_check_new_reminders' => [
        'classname'    => '\local_mychatbot\external\check_new_reminders',
        'description'  => 'Check whether there are new reminders for the user.',
        'type'         => 'read',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_teacher_courses' => [
        'classname'    => '\local_mychatbot\external\get_teacher_courses',
        'description'  => 'Get the courses for which the user is a teacher.',
        'type'         => 'read',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_analyze_course_progress' => [
        'classname'    => '\local_mychatbot\external\analyze_course_progress',
        'description'  => 'Truy vấn dữ liệu học viên và gọi FastAPI để lấy nhận xét',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_analyze_student_progress' => [
        'classname'    => '\local_mychatbot\external\analyze_student_progress',
        'description'  => 'Lấy điểm Quiz, Assignment của 1 học viên cụ thể và gọi AI phân tích',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_generate_quiz' => [
        'classname'    => '\local_mychatbot\external\generate_quiz',
        'description'  => 'Gửi yêu cầu tạo Quiz (kèm file base64) sang FastAPI',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_save_quiz_questions' => [
        'classname'    => '\local_mychatbot\external\save_quiz_questions',
        'description'  => 'Lưu danh sách câu hỏi JSON vào Ngân hàng câu hỏi của khóa học',
        'type'         => 'write',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_get_quiz_gen_history' => [
        'classname'    => '\local_mychatbot\external\get_quiz_gen_history',
        'description'  => 'Lấy lịch sử tạo quiz của người dùng giảng viên',
        'type'         => 'read',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
    'local_mychatbot_check_capability' => [
        'classname'    => '\local_mychatbot\external\check_capability',
        'description'  => 'Check the capabilities of the current user',
        'type'         => 'read',
        'ajax'         => true,
        'capabilities' => 'local/mychatbot:use',
    ],
];