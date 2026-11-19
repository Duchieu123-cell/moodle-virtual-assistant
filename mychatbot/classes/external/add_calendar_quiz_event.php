<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class add_calendar_quiz_event extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'suggestionid' => new external_value(PARAM_INT, 'ID from quiz_suggestions table')
        ]);
    }

    public static function execute($suggestionid) {
        global $DB, $USER, $CFG;

        $suggestion = $DB->get_record(
            'local_mychatbot_quiz_time_suggestions',
            ['id' => $suggestionid, 'userid' => $USER->id]
        );

        // Kiểm tra nếu đã accepted rồi thì báo lỗi
        if ($suggestion->accepted == 1) {
            return [
                'status'  => 'warning',
                'message' => 'Sự kiện này đã được thêm vào lịch rồi.'
            ];
        }

        require_once($CFG->dirroot . '/calendar/lib.php');

        $event = new \stdClass();
        $event->name = 'Thời gian đề xuất cho quiz ' . $suggestion->quizname . ', khóa ' . $suggestion->coursename;
        $event->format = 1; // FORMAT_HTML
        
        // Tạo mô tả có chứa link đến bài quiz
        $quiz_url = new \moodle_url('/mod/quiz/view.php', ['id' => $suggestion->cmid]);
        $description = 'Hãy thực hiện quiz đúng hạn để đạt kết quả tốt nhé.<br>';
        $description .= '<a href="' . $quiz_url->out() . '">Nhấn vào đây để chuyển hướng đến quiz và bắt đầu làm bài.</a>';
        $event->description = $description;

        $event->courseid = 0; // 0 = Sự kiện cá nhân (User Event), không gắn cứng vào lịch khóa học
        $event->groupid = 0;
        $event->userid = $USER->id;
        $event->modulename = 0; // Để 0 vì đây là User Event
        $event->instance = 0;
        $event->eventtype = 'user'; // Loại sự kiện: User
        
        $event->timestart = $suggestion->suggestedtime;
        $event->timeduration = 0; // Mặc định sự kiện kéo dài 1 tiếng (hoặc 0 nếu muốn point-in-time)
        $event->visible = 1;

        // Tạo sự kiện bằng Calendar API
        try {
            $calendarevent = \calendar_event::create($event);

            // --- CẬP NHẬT TRẠNG THÁI ACCEPTED ---
            $suggestion->accepted = 1;
            $DB->update_record('local_mychatbot_quiz_time_suggestions', $suggestion);
            // ------------------------------------
            // --- Thêm event vào bảng local_mychatbot_quiz_time_suggestion_calendar_events ---
            $calendareventrecord = new \stdClass();
            $calendareventrecord->userid = $USER->id;
            $calendareventrecord->calendareventid = $calendarevent->id;
            $calendareventrecord->quizid = $suggestion->quizid;
            $DB->insert_record('local_mychatbot_quiz_time_suggestion_calendar_events', $calendareventrecord);
            // ------------------------------------

            return [
                'status'  => 'success',
                'message' => 'Đã thêm vào lịch thành công!'
            ];
        } catch (\Exception $e) {
            throw new \moodle_exception('Lỗi khi tạo sự kiện lịch: ' . $e->getMessage());
        }
    }

    public static function execute_returns() {
        return new external_single_structure([
            'status'  => new external_value(PARAM_RAW, 'Status'),
            'message' => new external_value(PARAM_RAW, 'Message')
        ]);
    }
}