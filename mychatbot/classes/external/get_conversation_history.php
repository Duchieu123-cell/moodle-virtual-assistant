<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class get_conversation_history extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'conversationid' => new external_value(PARAM_INT, 'Conversation ID')
        ]);
    }

    public static function execute($conversationid) {
        global $DB, $USER;
        
        // (Bảo mật) Xác thực user sở hữu cuộc trò chuyện này
        if (!$DB->record_exists('local_mychatbot_conversation_titles', ['id' => $conversationid, 'userid' => $USER->id])) {
            throw new \moodle_exception('ID cuộc trò chuyện không hợp lệ hoặc không có quyền truy cập.');
        }

        // Lấy tất cả tin nhắn, sắp xếp theo cái cũ nhất
        $messages = $DB->get_records(
            'local_mychatbot_conversation_history', 
            ['conversationid' => $conversationid], 
            'timecreated ASC',
            'id, usermessage, botresponse, timecreated'
        );
        $history_data = [];
        foreach ($messages as $msg) {
            $fileinfos = [];
            $websearchinfos = [];
            if ($DB->record_exists('local_mychatbot_rag_file_references', ['historyid' => $msg->id])) {
                $fileinfos = $DB->get_records(
                    'local_mychatbot_rag_file_references',
                    ['historyid' => $msg->id],
                    'filename ASC',
                    'filename, fileurl, pagenumber'
                );
            }
            if ($DB->record_exists('local_mychatbot_rag_web_references', ['historyid' => $msg->id])) {
                $websearchinfos = $DB->get_records(
                    'local_mychatbot_rag_web_references',
                    ['historyid' => $msg->id],
                    'title ASC',
                    'title, url'
                );
            }
            $history_data[] = [
                'usermessage'    => $msg->usermessage,
                'botresponse'    => $msg->botresponse,
                'timecreated'    => $msg->timecreated,
                'fileinfos'      => array_values($fileinfos),
                'websearchinfos' => array_values($websearchinfos)

            ];
        }
        return $history_data;
    }

    public static function execute_returns() {
        // Trả về một MẢNG các tin nhắn
        return new external_multiple_structure(
            new external_single_structure([
                'usermessage'  => new external_value(PARAM_RAW, 'User message'),
                'botresponse'  => new external_value(PARAM_RAW, 'Bot response'),
                'timecreated'  => new external_value(PARAM_INT, 'Time created'),
                'fileinfos'    => new external_multiple_structure(
                    new external_single_structure([
                        'filename'   => new external_value(PARAM_RAW, 'File name'),
                        'fileurl'    => new external_value(PARAM_RAW, 'File URL'),
                        'pagenumber' => new external_value(PARAM_INT, 'Page number')
                    ])
                ),
                'websearchinfos' => new external_multiple_structure(
                    new external_single_structure([
                        'title' => new external_value(PARAM_RAW, 'Web search title'),
                        'url'   => new external_value(PARAM_RAW, 'Web search URL')
                    ])
                )
            ])
        );
    }
}