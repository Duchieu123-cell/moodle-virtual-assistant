<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class generate_quiz extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'prompt'        => new external_value(PARAM_RAW, 'Chủ đề/Yêu cầu', VALUE_DEFAULT, ''),
            'num_easy'      => new external_value(PARAM_INT, 'Số lượng câu hỏi dễ', VALUE_DEFAULT, 0),
            'num_medium'    => new external_value(PARAM_INT, 'Số lượng câu hỏi trung bình', VALUE_DEFAULT, 0),
            'num_hard'      => new external_value(PARAM_INT, 'Số lượng câu hỏi khó', VALUE_DEFAULT, 0),
            'filename'      => new external_value(PARAM_RAW, 'Tên file', VALUE_DEFAULT, ''),
            'filedata'      => new external_value(PARAM_RAW, 'Nội dung file (Base64)', VALUE_DEFAULT, ''),
            'userrequest'   => new external_value(PARAM_RAW, 'Nội dung của yêu cầu tạo quiz', VALUE_DEFAULT, '')
        ]);
    }
    /**
     * Nhận dữ liệu từ JS, gọi FastAPI và trả về kết quả
     */
    public static function execute($prompt, $num_easy, $num_medium, $num_hard, $filename, $filedata, $userrequest) {
        global $DB, $USER;


        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }


        // Chuẩn bị dữ liệu gửi đi (sẽ gửi dưới dạng multipart/form-data)
        $post_fields = [
            'prompt'        => $prompt,
            'num_easy'      => $num_easy,
            'num_medium'    => $num_medium,
            'num_hard'      => $num_hard
        ];

        // Xử lý file nếu giảng viên có tải lên
        if (!empty($filedata) && !empty($filename)) {
            // make_request_directory() là hàm chuẩn của Moodle tạo thư mục tạm
            // Thư mục và file trong này sẽ TỰ ĐỘNG BỊ XÓA khi PHP chạy xong
            $tempdir = make_request_directory(); 
            $tempfile = $tempdir . '/' . $filename;
            
            // Đảm bảo lọc bỏ header của base64 nếu JS lỡ gửi kèm 
            // (ví dụ: data:application/pdf;base64,JVBERi0...)
            $base64_string = $filedata;
            if (strpos($base64_string, ',') !== false) {
                $base64_string = explode(',', $base64_string)[1];
            }
            
            // Tạo file vật lý trên server Moodle
            file_put_contents($tempfile, base64_decode($base64_string));
            
            // Lấy mime type (ví dụ: application/pdf)
            $mime_type = mime_content_type($tempfile) ?: 'application/octet-stream';
            
            // Khởi tạo CURLFile - Đây là class PHP chuẩn để upload file
            $post_fields['file'] = new \CURLFile($tempfile, $mime_type, $filename);
        }
        // Kiểm tra quyền hạn (Giảng viên)
        // $context = \context_course::instance($courseid);
        // if (!has_capability('moodle/grade:viewall', $context) && !has_capability('moodle/course:update', $context)) {
        //     throw new \moodle_exception('nopermissions', 'error', '', 'Bạn không có quyền xem chi tiết trong khóa học này');
        // }

        // 3. GỌI API FASTAPI
        $fastapi_url = $base_url . '/generate_quiz';
        $ch = \curl_init();
        \curl_setopt($ch, CURLOPT_URL, $fastapi_url);
        \curl_setopt($ch, CURLOPT_POST, 1);
        // Truyền thẳng mảng $post_fields vào CURLOPT_POSTFIELDS
        // Khi thấy CURLFile, cURL sẽ tự động set header Content-Type thành multipart/form-data
        \curl_setopt($ch, CURLOPT_POSTFIELDS, $post_fields);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        \curl_setopt($ch, CURLOPT_TIMEOUT, 60);

        $response_json = \curl_exec($ch);
        $httpcode = \curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = \curl_error($ch);
        \curl_close($ch);
        if ($curl_error) {
            throw new \moodle_exception('cURL Error: ' . $curl_error);
        }
        if ($httpcode >= 400) {
            throw new \moodle_exception('API Error: ' . $httpcode . ' - ' . $response_json);
        }

        $response_object = json_decode($response_json);

        $new_quiz_gen_req = new \stdClass();
        $new_quiz_gen_req->userid = $USER->id;
        $new_quiz_gen_req->userrequest = $userrequest;
        $new_quiz_gen_req->timecreated = time();
        $new_quiz_gen_req->saved = 0;
        $new_quiz_gen_req->timesaved = 0;
        $new_quiz_gen_req->saved_in_course = '';
        $quiz_gen_req_id = $DB->insert_record('local_mychatbot_quiz_gen_request', $new_quiz_gen_req);

        $questions = $response_object->questions;
        $questions_for_return = [];
        foreach ($questions as $question) {
            $new_question = new \stdClass();
            $new_question->requestid = $quiz_gen_req_id;
            $new_question->question_text = $question->question_text;
            $new_question->first_option = $question->options[0];
            $new_question->second_option = $question->options[1];
            $new_question->third_option = $question->options[2];
            $new_question->fourth_option = $question->options[3];
            $new_question->correct_answer_index = $question->correct_answer_index;
            $new_question->explanation = $question->explanation;
            $new_question->saved = 0; // Mặc định là chưa lưu vào ngân hàng câu hỏi của khóa học nào
            $level = 'unknown';
            if (stripos($question->cognitive_level, 'Remember') !== false) {
                $level = 'easy';
            } else if (stripos($question->cognitive_level, 'Understand') !== false) {
                $level = 'medium';
            } else {
                $level = 'hard';
            }
            $new_question->level = $level;
            $question_id = $DB->insert_record('local_mychatbot_quiz_gen_questions', $new_question);
            $questions_for_return[] = [
                'question_id'          => $question_id,
                'question_text'        => $question->question_text,
                'options'              => $question->options,
                'correct_answer_index' => $question->correct_answer_index,
                'explanation'          => $question->explanation,
                'level'                => $level
            ];
        }

        return [
            'questions'  => $questions_for_return,
            'request_id' => $quiz_gen_req_id
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'questions'  => new external_multiple_structure(
                new external_single_structure([
                    'question_id'          => new external_value(PARAM_INT, 'ID của câu hỏi'),
                    'question_text'        => new external_value(PARAM_RAW, 'Nội dung câu hỏi'),
                    'options'              => new external_multiple_structure(
                        new external_value(PARAM_RAW, 'Tùy chọn')
                    ),
                    'correct_answer_index' => new external_value(PARAM_INT, 'Chỉ số đáp án đúng'),
                    'explanation'          => new external_value(PARAM_RAW, 'Giải thích'),
                    'level'                => new external_value(PARAM_RAW, 'Độ khó: easy, medium, hard, unknown')
                ])
            ),
            'request_id' => new external_value(PARAM_INT, 'ID của yêu cầu tạo quiz')
        ]);
    }
}