<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class set_reminder_setting extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'status'       => new external_value(PARAM_INT, 'New status: 1 for on, 0 for off'),
            'remindertime' => new external_value(PARAM_INT, 'Reminder time hour (8, 13, or 21)')
        ]);
    }

    public static function execute($status, $remindertime) {
        global $USER, $DB;
        $setting = $DB->get_record('local_mychatbot_daily_reminder_register', ['userid' => $USER->id]);
        
        // Cập nhật giá trị
        $setting->registered = ($status == 1) ? 1 : 0;
        // Xác thực giá trị time
        if (in_array($remindertime, [8, 13, 21])) {
            $setting->remindertime = $remindertime;
        } else {
            $setting->remindertime = 21; // Mặc định về 21 nếu sai
        }
        $DB->update_record('local_mychatbot_daily_reminder_register', $setting);

        return ['success' => true];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'success' => new external_value(PARAM_BOOL, 'True if successful')
        ]);
    }
}