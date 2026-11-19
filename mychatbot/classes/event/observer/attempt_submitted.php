<?php
namespace local_mychatbot\event\observer;

defined('MOODLE_INTERNAL') || die();

class attempt_submitted {
    /**
     * Bắt sự kiện \mod_quiz\event\attempt_submitted.
     * @param \mod_quiz\event\attempt_submitted $event Đối tượng sự kiện
     * @return void
     */
    public static function execute(\mod_quiz\event\attempt_submitted $event) {
        global $DB;
        $userid  = $event->userid;
        $quizid  = $event->other['quizid'];

        if (!$quizid || !$userid) {
            return;
        }

        # kiểm tra: trong tất cả lần làm bài quiz này, lần điểm cao nhất là bao nhiêu
        if (
            !$DB->record_exists(
                'local_mychatbot_quiz_doc_suggestion_content',
                ['userid' => $USER->id, 'quizid' => $response_object->doc_needed_quizid, 'type' => 'lowscore']
            )
        ) {
            $sql = "SELECT MAX(qa.sumgrades) AS maxgrade
                    FROM {quiz_attempts} AS qa
                    WHERE qa.quiz = ?
                    AND qa.userid = ?
                    AND qa.state = 'finished'";

            $maxgrade_record = $DB->get_record_sql($sql, [$quizid, $userid]);
            $totalgradeofquiz = $DB->get_field('quiz', 'sumgrades', ['id' => $quizid]);
            if ($maxgrade_record && $totalgradeofquiz > 0) {
                $percentage = ($maxgrade_record->maxgrade / $totalgradeofquiz) * 100;
                if ($percentage <= 65) {
                    // Nếu điểm cao nhất <= 65% thì thêm docs_needed_content type lowscore.
                    $courseid = $DB->get_field('quiz', 'course', ['id' => $quizid]);
                    $new_doc_needed = new \stdClass();
                    $new_doc_needed->userid = $userid;
                    $new_doc_needed->quizid = $quizid;
                    $new_doc_needed->courseid = $courseid;
                    $new_doc_needed->content = '...';
                    $new_doc_needed->timecreated = time();
                    $new_doc_needed->latest = 1;
                    $new_doc_needed->type = 'lowscore';
                    $DB->insert_record(
                        'local_mychatbot_quiz_doc_suggestion_content',
                        $new_doc_needed
                    );
                }
            }
        } else {
            // Nếu đã có thì check lại điểm cao nhất, nếu > 65% thì xóa bản ghi.
            $sql = "SELECT MAX(qa.sumgrades) AS maxgrade
                    FROM {quiz_attempts} AS qa
                    WHERE qa.quiz = ?
                    AND qa.userid = ?
                    AND qa.state = 'finished'";

            $maxgrade_record = $DB->get_record_sql($sql, [$quizid, $userid]);
            $totalgradeofquiz = $DB->get_field('quiz', 'sumgrades', ['id' => $quizid]);
            if ($maxgrade_record && $totalgradeofquiz > 0) {
                $percentage = ($maxgrade_record->maxgrade / $totalgradeofquiz) * 100;
                if ($percentage > 65) {
                    $DB->delete_records(
                        'local_mychatbot_quiz_doc_suggestion_content',
                        ['userid' => $userid, 'quizid' => $quizid, 'type' => 'lowscore']
                    );
                }
            }
        }

        if (
            $DB->record_exists(
                'local_mychatbot_quiz_doc_suggestion_content',
                ['userid' => $userid, 'quizid' => $quizid, 'content' => '...', 'type' => 'new']
            )
        ) {
            $DB->delete_records(
                'local_mychatbot_quiz_doc_suggestion_content',
                ['userid' => $userid, 'quizid' => $quizid, 'content' => '...', 'type' => 'new']
            );
        }

        if (
            !$DB->record_exists(
                'local_mychatbot_quiz_reminder_logs',
                ['userid' => $userid, 'quizid' => $quizid]
            )
        ) {
            return;
        }
        $reminded_quiz_log = $DB->get_record(
            'local_mychatbot_quiz_reminder_logs',
            ['userid' => $userid, 'quizid' => $quizid]
        );

        $user_bandit_arm = $DB->get_record(
            'local_mychatbot_quiz_reminder_bandit_arms',
            ['userid' => $userid, 'armid' => $reminded_quiz_log->armid]
        );

        if (!$user_bandit_arm) {
            return;
        }

        $user_bandit_arm->alpha = $user_bandit_arm->alpha + 1;

        $DB->delete_records(
            'local_mychatbot_quiz_reminder_logs',
            ['userid' => $userid, 'quizid' => $quizid]
        );

        $remain_reminded_quizzes = $DB->get_records(
            'local_mychatbot_quiz_reminder_logs',
            ['userid' => $userid]
        );

        if (!empty($remain_reminded_quizzes)) {
            foreach ($remain_reminded_quizzes as $quiz) {
                $time_close_of_quiz = $DB->get_record(
                    'quiz',
                    ['id' => $quiz->quizid],
                    'timeclose'
                );

                if ($time_close_of_quiz && $time_close_of_quiz->timeclose < time()) {
                    // Quiz đã đóng, tăng beta thêm 1.
                    $user_bandit_arm->beta = $user_bandit_arm->beta + 1;
                }
            }

            $DB->delete_records(
                'local_mychatbot_quiz_reminder_logs',
                ['userid' => $userid]
            );
        }

        $DB->update_record(
            'local_mychatbot_quiz_reminder_bandit_arms',
            $user_bandit_arm
        );

        // Gọi API để lấy nhắc nhở mới.
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }
        $user_arms_state = $DB->get_records(
            'local_mychatbot_quiz_reminder_bandit_arms',
            ['userid' => $userid],
            'armid ASC',
            'armid, alpha, beta'
        );

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
            return;
        }

        $sql_1 = "SELECT
                    q.id AS quiz_id,
                    q.name AS quiz_name,
                    q.timeclose AS quiz_timeclose,
                    q.timelimit AS quiz_timelimit,
                    cm.id AS course_module_id
                FROM {quiz} AS q
                JOIN {course_modules} AS cm ON q.id = cm.instance AND cm.course = q.course
                JOIN {modules} AS m ON cm.module = m.id
                WHERE q.course = ?
                AND m.name = 'quiz'
                AND cm.visible = 1
                AND cm.deletioninprogress = 0
                AND q.timeopen < UNIX_TIMESTAMP()
                AND q.timeclose > UNIX_TIMESTAMP()
                AND (
                    (NOT EXISTS (SELECT 1 FROM {quiz_attempts} AS qa WHERE qa.quiz = q.id AND qa.userid = ?)) OR
                    (EXISTS (SELECT 1 FROM {quiz_attempts} AS qa WHERE qa.quiz = q.id AND qa.userid = ? AND qa.state != 'finished'))
                )";

        $sql_2 = "SELECT COUNT(q.id)
                FROM {quiz} AS q
                JOIN {course_modules} AS cm ON q.id = cm.instance AND cm.course = q.course
                JOIN {modules} AS m ON cm.module = m.id
                WHERE q.course = ?
                AND m.name = 'quiz'
                AND cm.visible = 1
                AND cm.deletioninprogress = 0";

        $sql_3 = "SELECT COUNT(q.id)
                FROM {quiz} AS q
                JOIN {course_modules} AS cm ON q.id = cm.instance AND cm.course = q.course
                JOIN {modules} AS m ON cm.module = m.id
                WHERE q.course = ?
                AND m.name = 'quiz'
                AND cm.visible = 1
                AND cm.deletioninprogress = 0
                AND q.timeclose < UNIX_TIMESTAMP()
                AND NOT EXISTS (
                    SELECT 1
                    FROM {quiz_attempts} AS qa
                    WHERE qa.quiz = q.id
                    AND qa.userid = ?
                )";
        $reminder_data = [];
        foreach ($student_courses as $course) {
            $quizzes = $DB->get_records_sql($sql_1, [$course['course_id'], $USER->id, $USER->id]);
            if (!empty($quizzes)) {
                $total_quizzes_of_course = $DB->count_records_sql($sql_2, [$course['course_id']]);
                $missed_quizzes_count = $DB->count_records_sql($sql_3, [$course['course_id'], $USER->id]);
                $reminder_data[] = [
                    'course_name'             => $course['course_name'],
                    'total_quizzes_of_course' => $total_quizzes_of_course,
                    'missed_quizzes_count'    => $missed_quizzes_count,
                    'quizzes'                 => array_values($quizzes)
                ];
            }
        };

        if (empty($reminder_data)) {
            return;
        }
            
        $postdata = [
            'user_id'       => $USER->id,
            'time_now'      => time(),
            'arms_state'    => array_values($user_arms_state),
            'reminder_data' => $reminder_data
        ];
        $reminder_endpoint = $base_url . "/reminder/quiz";
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

        if (
            $response_object->doc_needed_quizid !== 0 && 
            !$DB->record_exists(
                'local_mychatbot_quiz_doc_suggestion_content',
                ['userid' => $USER->id, 'quizid' => $response_object->doc_needed_quizid]
            )
        ) {
            $courseid = $DB->get_field('quiz', 'course', ['id' => $response_object->doc_needed_quizid]);
            $new_doc_needed = new \stdClass();
            $new_doc_needed->userid = $USER->id;
            $new_doc_needed->quizid = $response_object->doc_needed_quizid;
            $new_doc_needed->courseid = $courseid;
            $new_doc_needed->content = '...';
            $new_doc_needed->timecreated = time();
            $new_doc_needed->latest = 1;
            $new_doc_needed->type = 'new';
            $DB->insert_record(
                'local_mychatbot_quiz_doc_suggestion_content',
                $new_doc_needed
            );
        }
        
        foreach ($response_object->reminded_quizzes as $reminded_quiz) {
            $new_record = new \stdClass();
            $new_record->userid = $USER->id;
            $new_record->quizid = $reminded_quiz->quiz_id;
            $new_record->armid = $reminded_quiz->arm_id;
            $new_record->timecreated = time();
            $DB->insert_record('local_mychatbot_quiz_reminder_logs', $new_record);
        }

        $DB->delete_records('local_mychatbot_quiz_reminders', ['userid' => $USER->id]);
        $newreminder = new \stdClass();
        $newreminder->userid = $USER->id;
        $newreminder->content = $response_object->response;
        $newreminder->timecreated = time();
        $newreminder->latest = 1;
        $DB->insert_record('local_mychatbot_quiz_reminders', $newreminder);

        $DB->delete_records('local_mychatbot_quiz_reminder_formatted', ['userid' => $USER->id]);
        foreach ($response_object->formatted_quizzes as $formatted_quiz) {
            $new_record = new \stdClass();
            $new_record->userid = $USER->id;
            $new_record->content = $formatted_quiz->content;
            $new_record->course_module_id = $formatted_quiz->course_module_id;
            $new_record->severity_level = $formatted_quiz->severity_level;
            $DB->insert_record('local_mychatbot_quiz_reminder_formatted', $new_record);
        }

        $DB->delete_records('local_mychatbot_quiz_time_suggestion_titles', ['userid' => $USER->id]);
        $DB->delete_records('local_mychatbot_quiz_time_suggestions', ['userid' => $USER->id]);
        
        if ($response_object->suggestion_title !== '' && !empty($response_object->suggestion_list)) {
            $new_title = new \stdClass();
            $new_title->userid = $USER->id;
            $new_title->title = $response_object->suggestion_title;
            $new_title->timecreated = time();
            $DB->insert_record('local_mychatbot_quiz_time_suggestion_titles', $new_title);

            foreach ($response_object->suggestion_list as $suggestion) {
                $rec = new \stdClass();
                $rec->userid = $USER->id;
                $rec->quizid = $suggestion->quiz_id;
                $rec->quizname = $suggestion->quiz_name;
                $rec->coursename = $suggestion->course_name;
                $rec->cmid = $suggestion->course_module_id;
                $rec->suggestedtime = $suggestion->suggested_time;
                $rec->accepted = 0;
                $DB->insert_record('local_mychatbot_quiz_time_suggestions', $rec);
            }
        }
        return;
    }
}