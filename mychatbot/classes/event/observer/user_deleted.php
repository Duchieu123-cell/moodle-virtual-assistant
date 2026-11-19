<?php
namespace local_mychatbot\event\observer;
defined('MOODLE_INTERNAL') || die();

class user_deleted {
    /**
     * Bắt sự kiện \core\event\user_deleted.
     * @param \core\event\user_deleted $event Đối tượng sự kiện
     * @return void
     */
    public static function execute(\core\event\user_deleted $event) {
        global $DB;
        $userid = $event->objectid;
        
        $DB->delete_records('local_mychatbot_daily_reminder_register', ['userid' => $userid]);
        $DB->delete_records('local_mychatbot_quiz_reminder_bandit_arms', ['userid' => $userid]);
        return;
    }
}