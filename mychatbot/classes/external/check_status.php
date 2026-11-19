<?php
namespace local_mychatbot\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;

class check_status extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $USER;
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }

        $status_endpoint = $base_url . "/status";
        $ch = \curl_init();
        \curl_setopt($ch, CURLOPT_URL, $status_endpoint);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        \curl_setopt($ch, CURLOPT_HTTPGET, 1);
        \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Accept: application/json']);
        \curl_setopt($ch, CURLOPT_TIMEOUT, 15); // 15 seconds timeout
        $raw_response = \curl_exec($ch);
        $httpcode = \curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = \curl_error($ch);
        \curl_close($ch);
        if ($curl_error) {
            return [
                'status'        => 'error',
                'message'       => 'Không thể kết nối đến máy chủ Chatbot.',
                'user_fullname' => fullname($USER)
            ];
        }
        
        $decoded = json_decode($raw_response, true);
        if ($httpcode == 200 && json_last_error() === JSON_ERROR_NONE && isset($decoded['status']) && $decoded['status'] === 'ok') {
            return [
                'status'        => 'ok',
                'message'       => 'Chatbot sẵn sàng hoạt động',
                'user_fullname' => fullname($USER)
            ];
        }

        return [
            'status'        => 'error',
            'message'       => 'Chatbot không phản hồi đúng cách.',
            'user_fullname' => fullname($USER)
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'status'        => new external_value(PARAM_RAW, 'Chatbot status: ok or error'),
            'message'       => new external_value(PARAM_RAW, 'Chatbot status message'),
            'user_fullname' => new external_value(PARAM_RAW, 'Full name of the user')
        ]);
    }
}