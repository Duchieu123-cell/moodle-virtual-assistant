<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_assignment_reminder_history extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $USER, $DB;
        $cooldown = 60; // 1 minute
        // Kiểm tra cooldown
        $last = $DB->get_record(
            'local_mychatbot_assignment_reminders',
            ['userid' => $USER->id],
            'timecreated',
            IGNORE_MISSING
        );
        
        $timeelapsed = $last ? (time() - $last->timecreated) : $cooldown + 1;
        if ($timeelapsed > $cooldown) {
            // Cooldown đã qua, gọi API
            $base_url = get_config('local_mychatbot', 'fastapi_url');
            if (empty($base_url)) {
                throw new \moodle_exception('FastAPI URL is not configured.');
            }
            
            $enrolled_courses = enrol_get_users_courses($USER->id, true);
            $student_courses = [];
            foreach ($enrolled_courses as $course) {
                $context = \context_course::instance($course->id);
                if (has_capability('moodle/grade:viewall', $context) || has_capability('moodle/course:update', $context)) {
                    continue;
                }
                $student_courses[] = [
                    'course_id'   => $course->id,
                    'course_name' => $course->fullname
                ];
            }

            if (empty($student_courses)) {
                return [
                    'response'                           => "Bạn không tham gia học tập trong khóa học nào.",   
                    'allowed_submission_assignments'     => [],
                    'not_allowed_submission_assignments' => [],
                    'timecreated'                        => time()
                ];
            }

            $sql_1 = "SELECT
                        a.id AS assignment_id,
                        a.name AS assignment_name,
                        a.duedate AS assignment_duedate,
                        a.allowsubmissionsfromdate AS assignment_allowsubmissionsfromdate,
                        cm.id AS course_module_id
                    FROM {assign} AS a
                    JOIN {course_modules} AS cm ON a.id = cm.instance AND cm.course = a.course
                    JOIN {modules} AS m ON cm.module = m.id
                    WHERE a.course = ?
                    AND m.name = 'assign'
                    AND cm.visible = 1
                    AND cm.deletioninprogress = 0
                    AND a.duedate > UNIX_TIMESTAMP()
                    AND (
                        (NOT EXISTS (SELECT 1 FROM {assign_submission} AS asub WHERE asub.assignment = a.id AND asub.userid = ?)) OR
                        (EXISTS (SELECT 1 FROM {assign_submission} AS asub WHERE asub.assignment = a.id AND asub.userid = ? AND asub.status != 'submitted'))
                    )";
            
            $reminder_data = [];
            foreach ($student_courses as $course) {
                $assignments = $DB->get_records_sql($sql_1, [$course['course_id'], $USER->id, $USER->id]);
                if (!empty($assignments)) {
                    $reminder_data[] = [
                        'course_name'         => $course['course_name'],
                        'assignments_pending' => array_values($assignments)
                    ];
                }
            }
            if (empty($reminder_data)) {
                return [
                    'response'                           => "Bạn không có assignment nào cần nhắc nhở.",   
                    'allowed_submission_assignments'     => [],
                    'not_allowed_submission_assignments' => [],
                    'timecreated'                        => time()
                ];
            }

            $postdata = [
                'user_id'       => $USER->id,
                'time_now'      => time(),
                'reminder_data' => $reminder_data
            ];
            $reminder_endpoint = $base_url . "/reminder/assignment";
            
            $ch = \curl_init();
            \curl_setopt($ch, CURLOPT_URL, $reminder_endpoint);
            \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            \curl_setopt($ch, CURLOPT_POST, 1);
            \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($postdata));
            \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
            \curl_setopt($ch, CURLOPT_TIMEOUT, 25);
            
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
            $DB->delete_records('local_mychatbot_assignment_reminders', ['userid' => $USER->id]);
            $newreminder = new \stdClass();
            $newreminder->userid = $USER->id;
            $newreminder->content = $response_object->response;
            $newreminder->timecreated = time();
            $DB->insert_record('local_mychatbot_assignment_reminders', $newreminder);

            $DB->delete_records('local_mychatbot_assignment_reminder_allow', ['userid' => $USER->id]);
            foreach ($response_object->allowed_submission_assignments as $assignment) {
                $new_record = new \stdClass();
                $new_record->userid = $USER->id;
                $new_record->content = $assignment->content;
                $new_record->course_module_id = $assignment->course_module_id;
                $new_record->severity_level = $assignment->severity_level;
                $DB->insert_record('local_mychatbot_assignment_reminder_allow', $new_record);
            }

            $DB->delete_records('local_mychatbot_assignment_reminder_not_allow', ['userid' => $USER->id]);
            foreach ($response_object->not_allowed_submission_assignments as $assignment) {
                $new_record = new \stdClass();
                $new_record->userid = $USER->id;
                $new_record->content = $assignment->content;
                $new_record->course_module_id = $assignment->course_module_id;
                $new_record->severity_level = $assignment->severity_level;
                $DB->insert_record('local_mychatbot_assignment_reminder_not_allow', $new_record);
            }
            return [
                'response'                           => $response_object->response,   
                'allowed_submission_assignments'     => array_values($response_object->allowed_submission_assignments),
                'not_allowed_submission_assignments' => array_values($response_object->not_allowed_submission_assignments),
                'timecreated'                        => time()
            ];
        }
        $reminder = $DB->get_record(
            'local_mychatbot_assignment_reminders',
            ['userid' => $USER->id]
        );
        $allowed_submission_assignments = $DB->get_records(
            'local_mychatbot_assignment_reminder_allow',
            ['userid' => $USER->id],
            'id ASC',
            'content, course_module_id, severity_level'
        );
        $not_allowed_submission_assignments = $DB->get_records(
            'local_mychatbot_assignment_reminder_not_allow',
            ['userid' => $USER->id],
            'id ASC',
            'content, course_module_id, severity_level'
        );
        return [
            'response'                           => $reminder->content,
            'allowed_submission_assignments'     => array_values($allowed_submission_assignments),
            'not_allowed_submission_assignments' => array_values($not_allowed_submission_assignments),
            'timecreated'                        => $reminder->timecreated
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
                'response'                           => new external_value(PARAM_RAW, 'Reminder response text'),
                'allowed_submission_assignments'     => new external_multiple_structure(
                    new external_single_structure([
                        'content'          => new external_value(PARAM_RAW, 'Formatted assignment list'),
                        'course_module_id' => new external_value(PARAM_INT, 'module id of the assignment'),
                        'severity_level'   => new external_value(PARAM_INT, 'Severity level for the assignment reminder')
                    ])
                ),
                'not_allowed_submission_assignments' => new external_multiple_structure(
                    new external_single_structure([
                        'content'          => new external_value(PARAM_RAW, 'Formatted assignment list'),
                        'course_module_id' => new external_value(PARAM_INT, 'module id of the assignment'),
                        'severity_level'   => new external_value(PARAM_INT, 'Severity level for the assignment reminder')
                    ])
                ),
                'timecreated'                        => new external_value(PARAM_INT, 'Timestamp of when the reminder was created in seconds')
        ]);
    }
}