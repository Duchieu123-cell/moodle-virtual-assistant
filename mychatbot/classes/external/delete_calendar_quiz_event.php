<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class delete_calendar_quiz_event extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'suggestionid' => new external_value(PARAM_INT, 'ID from quiz_suggestions table')
        ]);
    }

    public static function execute($suggestionid) {
        global $DB, $USER, $CFG;
        require_once($CFG->dirroot . '/calendar/lib.php');
        $suggestion = $DB->get_record(
            'local_mychatbot_quiz_time_suggestions',
            ['id' => $suggestionid, 'userid' => $USER->id],
            '*',
            IGNORE_MISSING
        );

        // Kiểm tra nếu quiz suggestion đang ở trạng thái chưa được thêm vào lịch (sẽ không thể xóa) thì báo lỗi
        if ($suggestion->accepted == 0) {
             return [
                'status'  => 'warning',
                'message' => 'Sự kiện này chưa được thêm vào lịch nên không thể xóa.',
            ];
        }

        $calendareventrecord = $DB->get_record(
            'local_mychatbot_quiz_time_suggestion_calendar_events',
            ['userid' => $USER->id, 'quizid' => $suggestion->quizid],
            '*',
            IGNORE_MISSING
        );

        if (empty($calendareventrecord) || !($calendareventrecord->calendareventid)) {
            return [
                'status'  => 'warning',
                'message' => 'Không tìm thấy sự kiện lịch tương ứng để xóa.',
            ];
        }
        if ($calendareventrecord->calendareventid > 0) {
            try {
                // Tải sự kiện lịch từ Moodle
                $event = \calendar_event::load($calendareventrecord->calendareventid);
                // Xóa nó
                $event->delete();
            } catch (\Exception $e) {
                throw new \moodle_exception('Lỗi khi xóa sự kiện lịch: ' . $e->getMessage());
            }
        }
        // --- CẬP NHẬT TRẠNG THÁI ACCEPTED VỀ 0 ---
        $suggestion->accepted = 0;
        $DB->update_record('local_mychatbot_quiz_time_suggestions', $suggestion);
        // ------------------------------------
        // --- XÓA BẢN GHI TRONG BẢNG local_mychatbot_quiz_time_suggestion_calendar_events ---
        $DB->delete_records('local_mychatbot_quiz_time_suggestion_calendar_events', ['id' => $calendareventrecord->id]);
        return [
            'status' => 'success',
            'message' => 'Đã xóa khỏi lịch.'
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'status'  => new external_value(PARAM_RAW, 'Status'),
            'message' => new external_value(PARAM_RAW, 'Message')
        ]);
    }
}