<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class send_message extends external_api {

    private static function process_query_request_module($sql_code, $postdata) {
        global $DB;
        
        // Lấy URL từ Settings
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }

        $fix_sql_error_endpoint = $base_url . "/fix_sql";
        $answer_query_endpoint = $base_url . "/get_sql_answer";
        $max_retries = 2;
        $query_result = [];
        $error_msg = "";
        $is_success = false;
        
        // BƯỚC 1: Lấy mã SQL và chạy thử (Lặp tối đa 2 lần để AI tự sửa lỗi nếu có)
        for ($i = 0; $i < $max_retries; $i++) { 
            try {
                // Sử dụng Moodle $DB để chạy lệnh SELECT.
                // get_records_sql trả về mảng các Object chứa dữ liệu.
                $records = $DB->get_records_sql($sql_code);
                
                // Moodle trả về array các objects, ta chuyển thành array thuần túy để dễ gửi qua JSON
                if ($records) {
                    $query_result = array_values(array_map(function($item) {
                        return (array)$item;
                    }, $records));
                } else {
                    $query_result = array(); // Không có data thì trả về mảng rỗng
                }
                
                $is_success = true;
                break; // Thành công thì thoát vòng lặp ngay lập tức
                
            } catch (Exception $e) {
                // Nếu DB báo lỗi (sai cú pháp, cột không tồn tại...), ta bắt lỗi
                // và lưu lại để gửi cho chatbot server sửa.
                $error_msg = $e->getMessage();
            }
            
            // Nếu có lỗi, ta gửi kèm mã SQL cũ và thông báo lỗi để AI sửa
            if (!empty($error_msg)) {
                $postdata["previous_error_sql"] = $sql_code;
                $postdata["sql_error_msg"] = $error_msg;
            }

  
            $ch = \curl_init();
            \curl_setopt($ch, CURLOPT_URL, $fix_sql_error_endpoint);
            \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            \curl_setopt($ch, CURLOPT_POST, 1);
            \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($postdata));
            \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
            \curl_setopt($ch, CURLOPT_TIMEOUT, 45); // 45 seconds timeout
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
            $response_array = json_decode($raw_response, true);

            if (isset($response_array['sql_query'])) {
                $sql_code = $response_array['sql_query'];
            }
        }
        
        // BƯỚC 2: Gửi kết quả DB cho AI để dịch thành câu trả lời tự nhiên
        if ($is_success) {
            $answer_data = [
                "message"      => $postdata['message'],
                "sql_result"   => $query_result,
                "chat_history" => $postdata['chat_history']
            ];

            
            $ch = \curl_init();
            \curl_setopt($ch, CURLOPT_URL, $answer_query_endpoint);
            \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
            \curl_setopt($ch, CURLOPT_POST, 1);
            \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($answer_data));
            \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
            \curl_setopt($ch, CURLOPT_TIMEOUT, 45); // 45 seconds timeout
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

            $final_response = json_decode($raw_response);
            
            return $final_response;
        }
        
        // Nếu thử 2 lần vẫn lỗi, trả về câu xin lỗi mặc định
        return [
            "response" => "Xin lỗi, hiện tại tôi đang gặp chút khó khăn kỹ thuật khi tra cứu hệ thống. Bạn vui lòng thử lại sau nhé!"
        ];
    }

    private static function call_fastapi_post($postdata) {
        // Lấy URL từ Settings
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }

        $chat_endpoint = $base_url . "/chat";
        $ch = \curl_init();
        \curl_setopt($ch, CURLOPT_URL, $chat_endpoint);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        \curl_setopt($ch, CURLOPT_POST, 1);
        \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($postdata));
        \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        \curl_setopt($ch, CURLOPT_TIMEOUT, 60); // 60 seconds timeout
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

        if ($response_object->type === 'sql_response') {
            return self::process_query_request_module(
                $response_object->sql_query,
                $postdata
            );
        }

        return $response_object;
    }

    public static function execute_parameters() {
        return new external_function_parameters([
            'message'        => new external_value(PARAM_RAW, 'User message'),
            'conversationid' => new external_value(PARAM_INT, 'Conversation ID, 0 for new'),
            'timecreated'    => new external_value(PARAM_INT, 'Client timestamp')
        ]);
    }

    public static function execute($message, $conversationid, $timecreated) {
        global $DB, $USER;
        if (empty($timecreated)) {
            $timecreated = time();
        }

        $enrolled_courses = enrol_get_users_courses($USER->id, true);
        $role = 'student';
        foreach ($enrolled_courses as $course) {
            $context = \context_course::instance($course->id);
            if (has_capability('moodle/grade:viewall', $context) || has_capability('moodle/course:update', $context)) {
                $role = 'teacher';
                break;
            }
        }

        $newconversation = null; // Biến để trả về nếu tạo chat mới

        // --- Logic tạo cuộc trò chuyện mới ---
        if ($conversationid == 0) {
            $postdata = [
                'message'      => $message,
                'user_id'      => $USER->id,
                'role'         => $role,
                'chat_history' => [] // Không có lịch sử chat
            ];

            $response_object = self::call_fastapi_post($postdata);
            // Tạo tiêu đề cuộc trò chuyện từ phản hồi
            $title = preg_replace('/^\s+|\s+$/m', '', $message);
            if (strlen($title) > 30) {
                $title = substr($title, 0, 30) . ' ...';
            }
            
            $newtitle = new \stdClass();
            $newtitle->userid = $USER->id;
            $newtitle->title = $title;
            $newtitle->timecreated = $timecreated;
            $conversationid = $DB->insert_record('local_mychatbot_conversation_titles', $newtitle);
            // Chuẩn bị dữ liệu trả về cho JS trong trường hợp tạo cuộc trò chuyện mới
            $newconversation = ['id' => $conversationid, 'title' => $title];
            // Lưu lịch sử chat
            $history = new \stdClass();
            $history->conversationid = $conversationid;
            $history->usermessage = $message;
            $history->botresponse = $response_object->response;
            $history->timecreated = $timecreated;
            $historyid = $DB->insert_record('local_mychatbot_conversation_history', $history);
            // Lưu các file URLs nếu có
            if (isset($response_object->fileinfos) && !empty($response_object->fileinfos)) {
                foreach ($response_object->fileinfos as $fileinfo) {
                    $new_record = new \stdClass();
                    $new_record->historyid = $historyid;
                    $new_record->filename = $fileinfo->filename;
                    $new_record->fileurl = $fileinfo->fileurl;
                    $new_record->pagenumber = $fileinfo->pagenumber;
                    $DB->insert_record('local_mychatbot_rag_file_references', $new_record);
                } 
            }
            if (isset($response_object->websearchinfos) && !empty($response_object->websearchinfos)) {
                foreach ($response_object->websearchinfos as $webinfo) {
                    $new_record = new \stdClass();
                    $new_record->historyid = $historyid;
                    $new_record->title = $webinfo->title;
                    $new_record->url = $webinfo->url;
                    $DB->insert_record('local_mychatbot_rag_web_references', $new_record);
                } 
            }
            return [
                'response'        => $response_object->response,
                'newconversation' => $newconversation,
                'fileinfos'       => isset($response_object->fileinfos) ? array_values($response_object->fileinfos) : [],
                'websearchinfos'  => isset($response_object->websearchinfos) ? array_values($response_object->websearchinfos) : []
            ];
        }

        // (Bảo mật) Kiểm tra xem conversationid này có thuộc về user này không
        if (!$DB->record_exists('local_mychatbot_conversation_titles', ['id' => $conversationid, 'userid' => $USER->id])) {
            throw new \moodle_exception('Invalid conversation ID');
        }
        $chat_history = $DB->get_records(
            'local_mychatbot_conversation_history',
            ['conversationid' => $conversationid],
            'timecreated ASC',
            'usermessage, botresponse'
        );
        $refactored_history = [];

        // Cắt lấy tối đa 2 phần tử cuối cùng (mới nhất) từ mảng lịch sử
        $recent_history = array_slice($chat_history, -2);

        foreach ($recent_history as $entry) {
            $refactored_history[] = [
                'user_message'     => $entry->usermessage,
                'chatbot_response' => $entry->botresponse
            ];
        }
        $postdata = [
            'message'      => $message,
            'user_id'      => $USER->id,
            'role'         => $role,
            'chat_history' => $refactored_history
        ];
        $response_object = self::call_fastapi_post($postdata);
        
        // Lưu lịch sử chat
        $history = new \stdClass();
        $history->conversationid = $conversationid;
        $history->usermessage = $message;
        $history->botresponse = $response_object->response;
        $history->timecreated = $timecreated;
        $historyid = $DB->insert_record('local_mychatbot_conversation_history', $history);
        // Lưu các URLs nếu có
        if (isset($response_object->fileinfos) && !empty($response_object->fileinfos)) {
            foreach ($response_object->fileinfos as $fileinfo) {
                $new_record = new \stdClass();
                $new_record->historyid = $historyid;
                $new_record->filename = $fileinfo->filename;
                $new_record->fileurl = $fileinfo->fileurl;
                $new_record->pagenumber = $fileinfo->pagenumber;
                $DB->insert_record('local_mychatbot_rag_file_references', $new_record);
            }
        }
        if (isset($response_object->websearchinfos) && !empty($response_object->websearchinfos)) {
            foreach ($response_object->websearchinfos as $webinfo) {
                $new_record = new \stdClass();
                $new_record->historyid = $historyid;
                $new_record->title = $webinfo->title;
                $new_record->url = $webinfo->url;
                $DB->insert_record('local_mychatbot_rag_web_references', $new_record);
            } 
        }
        // Chuẩn bị dữ liệu trả về cho JS mặc định nếu không tạo cuộc trò chuyện mới
        $newconversation = ['id' => -1, 'title' => ''];
        return [
            'response'        => $response_object->response,
            'newconversation' => $newconversation,
            'fileinfos'       => isset($response_object->fileinfos) ? array_values($response_object->fileinfos) : [],
            'websearchinfos'  => isset($response_object->websearchinfos) ? array_values($response_object->websearchinfos) : []
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'response'        => new external_value(PARAM_RAW, 'Bot response text'),
            'newconversation' => new external_single_structure([
                'id'    => new external_value(PARAM_INT, 'New conversation ID'),
                'title' => new external_value(PARAM_RAW, 'New conversation title')
            ]),
            'fileinfos'       => new external_multiple_structure(
                new external_single_structure([
                    'filename'   => new external_value(PARAM_RAW, 'File name'),
                    'fileurl'    => new external_value(PARAM_RAW, 'File URL'),
                    'pagenumber' => new external_value(PARAM_INT, 'Page number')
                ])
            ),
            'websearchinfos'  => new external_multiple_structure(
                new external_single_structure([
                    'title' => new external_value(PARAM_RAW, 'Web search result title'),
                    'url'   => new external_value(PARAM_RAW, 'Web search result URL')
                ])
            )
        ]);
    }
}