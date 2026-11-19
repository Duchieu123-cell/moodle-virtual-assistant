<?php
namespace local_mychatbot\event\observer;

defined('MOODLE_INTERNAL') || die();

class user_created {
    /**
     * Bắt sự kiện \core\event\user_created.
     * @param \core\event\user_created $event Đối tượng sự kiện
     * @return void
     */
    public static function execute(\core\event\user_created $event) {
        global $DB;
        $userid = $event->objectid;

        if (!$user = $DB->get_record('user', ['id' => $userid])) {
            return false;
        }

        if (!$DB->record_exists('local_mychatbot_daily_reminder_register', ['userid' => $userid])) {
            $newsetting = new \stdClass();
            $newsetting->userid = $userid;
            $newsetting->registered = 1;
            $newsetting->remindertime = 21;
            $DB->insert_record('local_mychatbot_daily_reminder_register', $newsetting);
        }

        if (!$DB->record_exists('local_mychatbot_quiz_reminder_bandit_arms', ['userid' => $userid])) {
            for ($armid = 1; $armid <= 5; $armid++) {
                $record = new \stdClass();
                $record->userid = $userid;
                $record->armid = $armid;
                $record->alpha = 1;
                $record->beta = 1;
                $DB->insert_record('local_mychatbot_quiz_reminder_bandit_arms', $record);
            }
        }

        return;
    }
}