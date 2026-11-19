<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_quiz_gen_history extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $DB, $USER;
        
        // Lấy tất cả tin nhắn, sắp xếp theo cái cũ nhất
        $quiz_gen_reqs = $DB->get_records(
            'local_mychatbot_quiz_gen_request', 
            ['userid' => $USER->id], 
            'timecreated ASC'
        );

        $history_data = [];

        foreach ($quiz_gen_reqs as $req) {

            $request_id = $req->id;
            $questions = $DB->get_records(
                'local_mychatbot_quiz_gen_questions',
                ['requestid' => $request_id]
            );
            $refactor_questions = [];
            foreach ($questions as $question) {
                $refactor_questions[] = [
                    'question_id'          => $question->id,
                    'question_text'        => $question->question_text,
                    'options'              => [
                        $question->first_option,
                        $question->second_option,
                        $question->third_option,
                        $question->fourth_option,
                    ],
                    'correct_answer_index' => $question->correct_answer_index,
                    'explanation'          => $question->explanation,
                    'level'                => $question->level,
                    'saved'                => $question->saved
                ];
                
            }
            $history_data[] = [
                'request_id'      => $request_id,
                'userrequest'     => $req->userrequest,
                'timecreated'     => $req->timecreated,
                'saved'           => $req->saved,
                'timesaved'       => $req->timesaved,
                'saved_in_course' => $req->saved_in_course,
                'questions'       => $refactor_questions
            ];

        }

        return $history_data;
    }

    public static function execute_returns() {
        // Trả về một MẢNG các tin nhắn
        return new external_multiple_structure(
            new external_single_structure([
                'request_id'      => new external_value(PARAM_INT, 'Request ID'),
                'userrequest'     => new external_value(PARAM_RAW, 'User request'),
                'timecreated'     => new external_value(PARAM_INT, 'Time created'),
                'saved'           => new external_value(PARAM_INT, '1 if saved, 0 if not saved'),
                'timesaved'       => new external_value(PARAM_INT, 'Time saved'),
                'saved_in_course' => new external_value(PARAM_RAW, 'Tên khóa học mà đã lưu bộ câu hỏi vào ngân hàng câu hỏi của khóa học đó'),
                'questions'       => new external_multiple_structure(
                    new external_single_structure([
                        'question_id'          => new external_value(PARAM_INT, 'Question ID'),
                        'question_text'        => new external_value(PARAM_RAW, 'Question Text'),
                        'options'              => new external_multiple_structure(
                            new external_value(PARAM_RAW, 'Each of 4 answers')
                        ),
                        'correct_answer_index' => new external_value(PARAM_INT, 'Correct Answer Index'),
                        'explanation'          => new external_value(PARAM_RAW, 'Explanation'),
                        'level'                => new external_value(PARAM_RAW, 'Difficulty Level: easy, medium, hard, unknown'),
                        'saved'                => new external_value(PARAM_INT, '1 if saved, 0 if not saved')
                    ])
                )
            ])
        );
    }
}