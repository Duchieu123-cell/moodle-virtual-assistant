<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class save_quiz_questions extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'courseid'      => new external_value(PARAM_INT, 'ID khóa học'),
            'request_id'    => new external_value(PARAM_INT, 'ID của yêu cầu tạo quiz nhằm mục đích tracking để cập nhật cột saved của yêu cầu đó trong database'),
            'questionsjson' => new external_value(PARAM_RAW, 'Chuỗi JSON chứa danh sách câu hỏi')
        ]);
    }
    /**
     * Hàm xử lý chính: Parse JSON và Insert vào Database Moodle
     */
    public static function execute($courseid, $request_id, $questionsjson) {
        global $DB, $CFG;
        // Bắt buộc require thư viện question của Moodle
        require_once($CFG->libdir . '/questionlib.php');

        // 1. Xác thực tham số và quyền hạn
        $context = \context_course::instance($courseid);
        
        if (!has_capability('moodle/question:add', $context)) {
            throw new \moodle_exception('nopermissions', 'error', '', 'Bạn không có quyền thêm câu hỏi vào khóa học này.');
        }

        // 2. Giải mã JSON
        $questions = json_decode($questionsjson, true);
        if (!$questions || !is_array($questions)) {
            return array('status' => 'error', 'message' => 'Dữ liệu câu hỏi từ AI không hợp lệ.');
        }

        // 3. Lấy danh mục câu hỏi (Category) mặc định của khóa học
        $category = question_get_default_category($context->id);
        if (!$category) {
            return [
                'status'  => 'error', 
                'message' => 'Không tìm thấy danh mục câu hỏi mặc định của khóa học.'
            ];
        }

        // 4. Lặp qua từng câu hỏi và tạo object theo chuẩn Moodle
        $qtype = \question_bank::get_qtype('multichoice');
        $saved_count = 0;

        foreach ($questions as $qdata) {
            $question = new \stdClass();
            $question->category = $category->id;
            $question->qtype = 'multichoice';
            $question->contextid = $context->id;
            
            // Tên câu hỏi (Moodle giới hạn 255 ký tự, ta cắt lấy 50 ký tự đầu của nội dung làm tên)
            $question->name = 'Câu hỏi được tạo: ' . mb_substr(strip_tags($qdata['question_text']), 0, 50) . '...';
            if (empty(trim($question->name))) {
                $question->name = 'Câu hỏi được tạo: ' . time();
            }

            // Nội dung chính và giải thích
            $question->questiontext = array('text' => $qdata['question_text'], 'format' => FORMAT_HTML);
            $question->generalfeedback = array('text' => $qdata['explanation'] ?? '', 'format' => FORMAT_HTML);
            
            // Các cài đặt mặc định cho câu hỏi trắc nghiệm
            $question->defaultmark = 1;
            $question->penalty = 0.3333333;
            $question->length = 1;
            $question->hidden = 0;
            $question->single = 1; // 1 = Chỉ chọn 1 đáp án đúng
            $question->shuffleanswers = 1; // Đảo đáp án
            $question->answernumbering = 'abc'; // Đánh số a, b, c
            
            // Các chuỗi phản hồi mặc định
            $question->correctfeedback = array('text' => 'Câu trả lời chính xác.', 'format' => FORMAT_HTML);
            $question->partiallycorrectfeedback = array('text' => 'Câu trả lời đúng một phần.', 'format' => FORMAT_HTML);
            $question->incorrectfeedback = array('text' => 'Câu trả lời sai.', 'format' => FORMAT_HTML);

            // Gắn các đáp án (options)
            $question->answer = array();
            $question->fraction = array(); // Tỷ lệ điểm (1.0 = 100%, 0.0 = 0%)
            $question->feedback = array();

            foreach ($qdata['options'] as $idx => $optText) {
                $question->answer[] = array('text' => $optText, 'format' => FORMAT_HTML);
                // Nếu index hiện tại khớp với correct_answer_index do AI sinh ra thì cho 1.0 điểm
                $question->fraction[] = ($idx == $qdata['correct_answer_index']) ? 1.0 : 0.0;
                $question->feedback[] = array('text' => '', 'format' => FORMAT_HTML);
            }

            // Gọi hàm save_question lõi của Moodle để insert vào DB
            $saved_question = $qtype->save_question($question, $question);
            if (!empty($saved_question->id)) {
                $saved_count++;
            }

            // Đánh dấu câu hỏi đã được lưu
            $question_record = $DB->get_record(
                'local_mychatbot_quiz_gen_questions', 
                ['id' => $qdata['question_id']]
            );
            $question_record->saved = 1;
            $DB->update_record('local_mychatbot_quiz_gen_questions', $question_record);
            
        }

        // Cập nhật trạng thái của yêu cầu tạo quiz trong database
        $quiz_gen_req = $DB->get_record(
            'local_mychatbot_quiz_gen_request', 
            ['id' => $request_id]
        );
        $course_name = $DB->get_field('course', 'fullname', ['id' => $courseid]);
        $quiz_gen_req->saved = 1; // Đánh dấu đã lưu xong
        $quiz_gen_req->timesaved = time(); // Ghi lại thời gian lưu
        $quiz_gen_req->saved_in_course = $course_name; // Ghi lại tên của khóa học đã lưu

        $DB->update_record('local_mychatbot_quiz_gen_request', $quiz_gen_req);

        return [
            'status'  => 'success',
            'message' => "Tuyệt vời! Đã lưu thành công {$saved_count} câu hỏi vào ngân hàng câu hỏi."
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'status'  => new external_value(PARAM_RAW, 'Trạng thái của yêu cầu'),
            'message' => new external_value(PARAM_RAW, 'Thông điệp phản hồi chi tiết')
        ]);
    }
}