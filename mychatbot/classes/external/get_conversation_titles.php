<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_conversation_titles extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([]);
    }

    public static function execute() {
        global $DB, $USER;
        // Lấy tất cả, sắp xếp theo cái mới nhất
        $titles = $DB->get_records(
            'local_mychatbot_conversation_titles', 
            ['userid' => $USER->id], 
            'timecreated DESC', 
            'id, title, timecreated'
        );
        // Chuyển đổi từ object (key là id) sang array (key là số)
        return array_values($titles);
    }

    public static function execute_returns() {
        // Trả về một MẢNG các tiêu đề
        return new external_multiple_structure(
            new external_single_structure([
                'id'          => new external_value(PARAM_INT, 'Conversation ID'),
                'title'       => new external_value(PARAM_RAW, 'Conversation title'),
                'timecreated' => new external_value(PARAM_INT, 'Time created')
            ])
        );
    }
}