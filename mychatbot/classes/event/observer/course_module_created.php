<?php
namespace local_mychatbot\event\observer;

defined('MOODLE_INTERNAL') || die();

class course_module_created {
    /**
     * Bắt sự kiện \core\event\course_module_created.
     * @param \core\event\course_module_created $event Đối tượng sự kiện
     * @return void
     */
    public static function execute(\core\event\course_module_created $event) {
        global $DB;
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        // 1. Kiểm tra xem module này có phải là 'resource' (File PDF/Word...) không
        // Tên module trong bảng mdl_modules là 'resource'
        if ($event->other['modulename'] !== 'resource') {
            return;
        }

        $contextid = $event->contextid;
        // 2. Lấy file từ Storage API của Moodle
        // Component của resource module là 'mod_resource', filearea là 'content'
        $fs = get_file_storage();
        $files = $fs->get_area_files(
            $contextid,
            'mod_resource',
            'content',
            0,
            'sortorder DESC',
            false
        ); 
        if (empty($files)) {
            return;
        }

        // Lấy file chính (thường là file đầu tiên không phải thư mục)
        $file = reset($files); 
        
        if (
            $file->get_mimetype() !== 'application/pdf' &&
            $file->get_mimetype() !== 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' &&
            $file->get_mimetype() !== 'text/plain'
        ) {
            return;
        }

        // 3. Chuẩn bị gửi sang fastapi
        $upload_file_endpoint =  $base_url . '/ingest/file';
        
        // Copy file nội bộ ra temp để gửi (cách an toàn nhất)
        $temppath = make_request_directory() . '/' . $file->get_filename();
        $file->copy_content_to($temppath);

        // 4. Gửi bằng Curl
        $ch = \curl_init();
        $cfile = new \CURLFile($temppath, $file->get_mimetype(), $file->get_filename());
        $fileurl = \moodle_url::make_pluginfile_url(
            $file->get_contextid(),
            $file->get_component(),
            $file->get_filearea(),
            $file->get_itemid(),
            $file->get_filepath(),
            $file->get_filename(),
            false
        );

        // --- BƯỚC THÊM MỚI: LẤY TÊN KHÓA HỌC ---
        // Sử dụng $DB để truy vấn bảng 'course' lấy trường 'fullname' dựa vào courseid của event
        $course = $DB->get_record('course', ['id' => $event->courseid], 'id, fullname');
        $course_name = $course ? $course->fullname : '';

        $data = [
            'file'        => $cfile,
            'mimetype'    => $file->get_mimetype(),
            'fileurl'     => $fileurl->out(false),
            'course_name' => $course_name
        ];

        \curl_setopt($ch, CURLOPT_URL, $upload_file_endpoint);
        \curl_setopt($ch, CURLOPT_POST, 1);
        \curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        
        // Timeout ngắn để không làm treo Moodle nếu chatbot server fastapi có vấn đề, vì đây là background task nên không cần chờ phản hồi lâu
        \curl_setopt($ch, CURLOPT_TIMEOUT, 5); 
        $response = \curl_exec($ch);
        \curl_close($ch);

        // Dọn dẹp file temp
        unlink($temppath);

        return;
    }
}