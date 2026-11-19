<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_current_quiz_suggestions extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $DB, $USER;
        $suggestions = $DB->get_records(
            'local_mychatbot_quiz_time_suggestions',
            ['userid' => $USER->id],
            'id ASC',
            'id, quizid, quizname, suggestedtime, accepted'
        );
        $suggestion_title = $DB->get_record(
            'local_mychatbot_quiz_time_suggestion_titles',
            ['userid' => $USER->id],
            'title',
            IGNORE_MISSING
        );
        if (!empty($suggestions) && !empty($suggestion_title)) {
            $list_suggestions = [];
            foreach ($suggestions as $suggestion) {
                $exists = $DB->record_exists(
                    'local_mychatbot_quiz_time_suggestion_calendar_events',
                    ['userid' => $USER->id, 'quizid' => $suggestion->quizid]
                );
                $list_suggestions[] = [
                    'id'            => $suggestion->id,
                    'quizname'      => $suggestion->quizname,
                    'suggestedtime' => $suggestion->suggestedtime,
                    'accepted'      => $suggestion->accepted,
                    'exists'        => $exists ? true : false
                ];
            }
            return [
                'title'       => $suggestion_title->title,
                'suggestions' => $list_suggestions,
                'timecreated' => $suggestion_title->timecreated
            ];
        }
        return [
            'title'       => '',
            'suggestions' => [],
            'timecreated' => time()
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'title'       => new external_value(PARAM_RAW, 'Suggestion Title'),
            'suggestions' => new external_multiple_structure(
                new external_single_structure([
                    'id'            => new external_value(PARAM_INT, 'Suggestion ID'),
                    'quizname'      => new external_value(PARAM_RAW, 'Quiz Name'),
                    'suggestedtime' => new external_value(PARAM_INT, 'Suggested Time (Unix Timestamp)'),
                    'accepted'      => new external_value(PARAM_INT, 'Accepted Status (1 = accepted, 0 = not accepted yet)'),
                    'exists'        => new external_value(PARAM_BOOL, 'Whether a calendar event for this quiz already exists')
                ])
            ),
            'timecreated' => new external_value(PARAM_INT, 'Time when the suggestion was created (Unix Timestamp)')
        ]);
    }
}