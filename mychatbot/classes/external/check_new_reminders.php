<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class check_new_reminders extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $USER, $DB;
        $quiz = 0;
        $assignment = 0;
        // check cho quiz reminders
        $quiz_cooldown = 60;
        $last = $DB->get_record(
            'local_mychatbot_quiz_reminders',
            ['userid' => $USER->id],
            'timecreated, latest',
            IGNORE_MISSING
        );
        if (!empty($last)) {
            $timeelapsed = $last ? (time() - $last->timecreated) : $quiz_cooldown + 1;

            if ($timeelapsed > $quiz_cooldown || $last->latest === 1) {
                $quiz += 1;
            }
        }
        
        // check cho quiz docs needed
        if (
            $DB->record_exists('local_mychatbot_quiz_doc_suggestion_content', ['userid' => $USER->id, 'content' => '...']) ||
            $DB->record_exists('local_mychatbot_quiz_doc_suggestion_content', ['userid' => $USER->id, 'latest' => 1])
        ) {
            $quiz += 1;
        }

        // check cho assignment reminders
        $assignment_cooldown = 60; // 1 minutes
        // Kiểm tra cooldown
        $last = $DB->get_record(
            'local_mychatbot_assignment_reminders',
            ['userid' => $USER->id],
            'timecreated',
            IGNORE_MISSING
        );
        if (!empty($last)) {
            $timeelapsed = $last ? (time() - $last->timecreated) : $assignment_cooldown + 1;

            if ($timeelapsed > $assignment_cooldown) {
                $assignment += 1;
            }
        }
        return [
            'quiz'       => $quiz,
            'assignment' => $assignment
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'quiz'       => new external_value(PARAM_INT, 'Number of new quiz reminders + doc needed'),
            'assignment' => new external_value(PARAM_INT, 'Number of new assignment reminders')
        ]);
    }
}