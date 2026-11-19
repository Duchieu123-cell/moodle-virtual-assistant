<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_doc_needed_for_quiz extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $USER, $DB;
        if (
            $DB->record_exists('local_mychatbot_quiz_doc_suggestion_content', ['userid' => $USER->id, 'content' => '...'])
        ) {
            $doc_needed_contents_sql = "SELECT *
                FROM {local_mychatbot_quiz_doc_suggestion_content} AS dnc
                WHERE dnc.userid = ?
                AND dnc.content = '...'
                ORDER BY dnc.timecreated ASC";

            $quizzes = $DB->get_recordset_sql($doc_needed_contents_sql, [$USER->id]);

            $sql = "SELECT q.id AS question_id, q.questiontext AS question_content
                    FROM {quiz_slots} qs
                    JOIN {question_references} qr ON qs.id = qr.itemid
                    JOIN (
                        SELECT questionbankentryid, MAX(version) AS max_version
                        FROM {question_versions}
                        GROUP BY questionbankentryid
                    ) latest_ver ON qr.questionbankentryid = latest_ver.questionbankentryid
                    JOIN {question_versions} qv ON latest_ver.questionbankentryid = qv.questionbankentryid AND latest_ver.max_version = qv.version
                    JOIN {question} q ON qv.questionid = q.id
                    WHERE qs.quizid = ?
                    AND qr.component = 'mod_quiz'
                    AND qr.questionarea = 'slot'
                    AND q.qtype IN ('multichoice', 'truefalse')
                    ORDER BY qs.slot ASC";
            $sql_answers = "SELECT qa.answer AS correct_answer
                            FROM {question_answers} qa
                            WHERE qa.question = ? AND qa.fraction > 0";

            $quizzes_data = [];
            $grade_for_call_api = 0;
            $sumgrade_for_call_api = 0;
            foreach ($quizzes as $quiz) {
                # kiểm tra lại cho trường hợp type 'lowscore', nếu điểm cao nhất trong các lần làm bài quiz này đã > 65% thì xóa record này và bỏ qua
                if ($quiz->type == 'lowscore') {
                    $sql_maxgrade = "SELECT MAX(qa.sumgrades) AS maxgrade
                                     FROM {quiz_attempts} AS qa
                                     WHERE qa.quiz = ?
                                     AND qa.userid = ?
                                     AND qa.state = 'finished'";

                    $maxgrade_record = $DB->get_record_sql($sql_maxgrade, [$quiz->quizid, $USER->id]);
                    $quiz_total_grade = $DB->get_field('quiz', 'sumgrades', ['id' => $quiz->quizid]);
                    if ($maxgrade_record && $quiz_total_grade > 0) {
                        $maxgrade_percentage = ($maxgrade_record->maxgrade / $quiz_total_grade) * 100;
                        if ($maxgrade_percentage > 65) {
                            // Xóa record và bỏ qua
                            $DB->delete_records(
                                'local_mychatbot_quiz_doc_suggestion_content',
                                ['userid' => $USER->id, 'quizid' => $quiz->quizid, 'content' => '...', 'type' => 'lowscore']
                            );
                            continue;
                        } else {
                            // Giữ nguyên record để gửi API
                            $grade_for_call_api = $maxgrade_record->maxgrade;
                            $sumgrade_for_call_api = $quiz_total_grade;
                        }
                    }
                }

                $questions = $DB->get_recordset_sql($sql, [$quiz->quizid]);
                if (!$questions->valid()) {
                    continue;
                }

                $quizname = $DB->get_field('quiz', 'name', ['id' => $quiz->quizid]);
                $questions_data = [];
                foreach ($questions as $question) {
                    $answers = $DB->get_recordset_sql($sql_answers, [$question->question_id]);
                    if (!$answers->valid()) {
                        continue;
                    }
                    $answers_data = [];
                    foreach ($answers as $ans) {
                        $answers_data[] = strip_tags($ans->correct_answer);
                    }
                    $questions_data[] = [
                        'question_content' => strip_tags($question->question_content),
                        'answers'          => $answers_data
                    ];
                    $answers->close();
                }

                $questions->close();
                
                $course_name = $DB->get_field('course', 'fullname', ['id' => $quiz->courseid]);

                if ($quiz->type == 'lowscore') {
                    $quizzes_data[] = [
                        'quiz_id'     => $quiz->quizid,
                        'quiz_name'   => $quizname,
                        'course_name' => $course_name,
                        'questions'   => $questions_data,
                        'type'        => 'lowscore',
                        'grade'       => $grade_for_call_api,
                        'sumgrade'    => $sumgrade_for_call_api
                    ];
                } else {
                    $quizzes_data[] = [
                        'quiz_id'     => $quiz->quizid,
                        'quiz_name'   => $quizname,
                        'course_name' => $course_name,
                        'questions'   => $questions_data,
                        'type'        => 'new'
                    ];
                }
            }
            $quizzes->close();

            // xử lý call api lấy tài liệu cần cho quiz ở đây
            $base_url = get_config('local_mychatbot', 'fastapi_url');
            if (empty($base_url)) {
                throw new \moodle_exception('FastAPI URL is not configured.');
            }

            $postdata = [
                'quizzes_data' => $quizzes_data
            ];
            $reminder_endpoint = $base_url . "/docs_suggest";
            $ch = \curl_init();
            \curl_setopt($ch, CURLOPT_URL, $reminder_endpoint);
            \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            \curl_setopt($ch, CURLOPT_POST, 1);
            \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($postdata));
            \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
            \curl_setopt($ch, CURLOPT_TIMEOUT, 60); // Set timeout to 60 seconds
            
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

            $docs_data = $response_object->docs_data;
            // Cập nhật dữ liệu trả về
            foreach ($docs_data as $doc) {
                $old_record = $DB->get_record(
                    'local_mychatbot_quiz_doc_suggestion_content',
                    ['userid' => $USER->id, 'quizid' => $doc->quiz_id]
                );
                $old_record->content = $doc->content;
                $DB->update_record('local_mychatbot_quiz_doc_suggestion_content', $old_record);
                // Thêm các fileinfo
                $fileinfos = array_values($doc->fileinfos);
                foreach ($fileinfos as $fileinfo) {
                    $fileinfo_record = new \stdClass();
                    $fileinfo_record->contentid = $old_record->id;
                    $fileinfo_record->filename = $fileinfo->filename;
                    $fileinfo_record->fileurl = $fileinfo->fileurl;
                    $fileinfo_record->pagenumber = $fileinfo->pagenumber;
                    $DB->insert_record('local_mychatbot_quiz_doc_suggestion_references', $fileinfo_record);
                }
            }
        }

        // Trả về bộ dữ liệu old và new
        $old = [];
        $new = [];
        $recs = $DB->get_records(
            'local_mychatbot_quiz_doc_suggestion_content',
            ['userid' => $USER->id],
            'timecreated ASC',
            '*'
        );
        foreach ($recs as $rec) {
            $fileinfos = $DB->get_records(
                'local_mychatbot_quiz_doc_suggestion_references',
                ['contentid' => $rec->id],
                'filename, fileurl, pagenumber'
            );
            $item = [
                'content'     => $rec->content,
                'timecreated' => $rec->timecreated,
                'fileinfos'   => array_values($fileinfos)
            ];
            if ($rec->latest == 1) {
                $new[] = $item;
                $rec->latest = 0;
                $DB->update_record('local_mychatbot_quiz_doc_suggestion_content', $rec);
            } else {
                $old[] = $item;
            }
        }
        return [
            'old' => $old,
            'new' => $new
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'old' => new external_multiple_structure(
                new external_single_structure([
                    'content'     => new external_value(PARAM_RAW, 'Formatted quiz list'),
                    'timecreated' => new external_value(PARAM_INT, 'Timestamp'),
                    'fileinfos'   => new external_multiple_structure(
                        new external_single_structure([
                            'filename'   => new external_value(PARAM_RAW, 'File name'),
                            'fileurl'    => new external_value(PARAM_RAW, 'File URL'),
                            'pagenumber' => new external_value(PARAM_INT, 'Page number')
                        ])
                    )
                ])
            ),
            'new' => new external_multiple_structure(
                new external_single_structure([
                    'content'     => new external_value(PARAM_RAW, 'Formatted quiz list'),
                    'timecreated' => new external_value(PARAM_INT, 'Timestamp'),
                    'fileinfos'   => new external_multiple_structure(
                        new external_single_structure([
                            'filename'   => new external_value(PARAM_RAW, 'File name'),
                            'fileurl'    => new external_value(PARAM_RAW, 'File URL'),
                            'pagenumber' => new external_value(PARAM_INT, 'Page number')
                        ])
                    )
                ])
            ),
        ]);
    }
}