<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class get_reminder_setting extends external_api {
    /**
     * Hàm trợ giúp: Lấy hoặc tạo cài đặt cho người dùng
     */
    private static function get_or_create_user_setting($userid) {
        global $DB;
        $setting = $DB->get_record('local_mychatbot_daily_reminder_register', ['userid' => $userid]);
        if ($setting) {
            return $setting;
        }
        // Nếu chưa tồn tại, tạo mới với giá trị mặc định (registered = 1, remindertime = 21).
        $newsetting = new \stdClass();
        $newsetting->userid = $userid;
        $newsetting->registered = 1;
        $newsetting->remindertime = 21;
        $newsetting->id = $DB->insert_record('local_mychatbot_daily_reminder_register', $newsetting);
        return $newsetting;
    }

    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $USER;
        $setting = self::get_or_create_user_setting($USER->id);
        return [
            'status'       => (int)$setting->registered,
            'remindertime' => (int)$setting->remindertime
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'status'       => new external_value(PARAM_INT, '1 for on, 0 for off'),
            'remindertime' => new external_value(PARAM_INT, 'Hour of the day for reminder (0-23)'),
        ]);
    }
}