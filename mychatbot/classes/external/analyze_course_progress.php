<?php
namespace local_mychatbot\external;
use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_value;
use core_external\external_single_structure;
use core_external\external_multiple_structure;

class analyze_course_progress extends external_api {
    public static function execute_parameters() {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'ID của khóa học được chọn')
        ]);
    }
    /**
     * Xử lý truy vấn dữ liệu học viên và gọi FastAPI để lấy nhận xét về tiến độ khóa học dựa trên courseid được chọn
     */
    public static function execute($courseid) {
        global $USER, $DB;
        $base_url = get_config('local_mychatbot', 'fastapi_url');
        if (empty($base_url)) {
            throw new \moodle_exception('FastAPI URL is not configured.');
        }
        // 1. Xác thực tham số và quyền hạn
        $context = \context_course::instance($courseid);
        
        if (!has_capability('moodle/grade:viewall', $context) && !has_capability('moodle/course:update', $context)) {
            throw new \moodle_exception('nopermissions', 'error', '', 'Bạn không có quyền giảng dạy trong khóa học này');
        }

        // 2. SQL Query: Lấy điểm tổng kết (Course Total) của tất cả học viên đang active
        $sql = "SELECT u.id, u.firstname, u.lastname, gg.finalgrade, gi.grademax
                  FROM {user} u
                  JOIN {user_enrolments} ue ON ue.userid = u.id
                  JOIN {enrol} e ON e.id = ue.enrolid
                  JOIN {grade_grades} gg ON gg.userid = u.id
                  JOIN {grade_items} gi ON gi.id = gg.itemid
                 WHERE e.courseid = :courseid
                   AND gi.courseid = :courseid2
                   AND gi.itemtype = 'course'
                   AND u.deleted = 0
                   AND u.suspended = 0";
                   
        $records = $DB->get_records_sql($sql, array('courseid' => $courseid, 'courseid2' => $courseid));

        // 3. Xử lý dữ liệu thô thành phần trăm và tính thống kê
        $students = [];
        $stats = [
            'total_students' => count($records),
            'good'           => 0, // >= 80%
            'average'        => 0, // 40% - 79%
            'poor'           => 0  // < 40% hoặc chưa có điểm
        ];

        foreach ($records as $rec) {
            // Xử lý trường hợp chưa có điểm (null) hoặc max = 0
            $finalgrade = (float)$rec->finalgrade;
            $grademax = (float)$rec->grademax;
            $percentage = ($grademax > 0) ? ($finalgrade / $grademax) * 100 : 0;
            
            // Phân loại thống kê
            if ($percentage >= 80) {
                $stats['good']++;
            } elseif ($percentage >= 40) {
                $stats['average']++;
            } else {
                $stats['poor']++;
            }

            $students[] = [
                'id'       => $rec->id,
                'fullname' => $rec->firstname . ' ' . $rec->lastname,
                'course_completion_percentage' => round($percentage, 2)
            ];
        }

        // Tính tỷ lệ % cho thống kê chung
        if ($stats['total_students'] > 0) {
            $stats['good_percent'] = round(($stats['good'] / $stats['total_students']) * 100, 1);
            $stats['average_percent'] = round(($stats['average'] / $stats['total_students']) * 100, 1);
            $stats['poor_percent'] = round(($stats['poor'] / $stats['total_students']) * 100, 1);
        }

        // 4. Sắp xếp mảng học viên theo % điểm từ cao xuống thấp
        usort($students, function($a, $b) {
            return $b['course_completion_percentage'] <=> $a['course_completion_percentage']; // Sắp xếp giảm dần
        });

        // 5. Lọc ra Top đầu (>= 80%) và Top cuối (< 40%) với tối đa 5 người mỗi nhóm
        
        // Nhóm giỏi: Lọc những người >= 80%
        $excellent_students = array_filter($students, function($s) {
            return $s['course_completion_percentage'] >= 80;
        });
        // Chỉ lấy tối đa 5 người cao nhất
        $top_students = array_slice($excellent_students, 0, 5); 

        // Nhóm yếu: Lọc những người < 40%
        $at_risk_students = array_filter($students, function($s) {
            return $s['course_completion_percentage'] < 40;
        });
        // Lấy tối đa 5 người có điểm thấp nhất (nằm ở cuối mảng)
        $bottom_students = array_slice($at_risk_students, -5, 5); 
        // Đảo ngược mảng để người có điểm thấp nhất đứng đầu danh sách yếu
        $bottom_students = array_reverse($bottom_students);

        // 6. Đóng gói Payload chuẩn bị gửi sang FastAPI
        $course_record = $DB->get_record('course', array('id' => $courseid), 'fullname');
        $payload = [
            'course_name'    => $course_record->fullname,
            'statistics'     => $stats,
            'top_performing' => $top_students,
            'at_risk'        => $bottom_students
        ];

        // 7. Gọi API FastAPI bằng cURL
        $fastapi_url = $base_url . '/analyze/course';
        $ch = \curl_init();
        \curl_setopt($ch, CURLOPT_URL, $fastapi_url);
        \curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
        \curl_setopt($ch, CURLOPT_POST, 1);
        \curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
        \curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
        \curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        
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
        // Xử lý kết quả trả về
        $bot_response = $response_object->response ?? 'Phân tích hoàn tất, nhưng không có nội dung phản hồi từ AI.';
        // Tạo chuỗi HTML có class 'student-detail-link' và data attribute để JS bắt sự kiện click
        $top_names_str = empty($top_students) ? "Không có học viên nào" : implode("", array_map(function($s) use ($courseid) { 
            return "<div class='student-detail-link' data-userid='{$s['id']}' data-courseid='{$courseid}' title='Click để xem chi tiết'>• " . $s['fullname'] . ' (' . $s['course_completion_percentage'] . '%)</div>'; 
        }, $top_students));

        $bottom_names_str = empty($bottom_students) ? "Không có học viên nào" : implode("", array_map(function($s) use ($courseid) { 
            return "<div class='student-detail-link' data-userid='{$s['id']}' data-courseid='{$courseid}' title='Click để xem chi tiết'>• " . $s['fullname'] . ' (' . $s['course_completion_percentage'] . '%)</div>'; 
        }, $bottom_students));
        // Trả về kèm dữ liệu chartdata
        return [
            'response'  => $bot_response,
            'chartdata' => [
                'good_percent'    => $stats['good_percent'] ?? 0,
                'average_percent' => $stats['average_percent'] ?? 0,
                'poor_percent'    => $stats['poor_percent'] ?? 0,
                'top_names'       => $top_names_str,
                'bottom_names'    => $bottom_names_str
            ]
        ];
    }

    public static function execute_returns() {
        return new external_single_structure([
            'response'  => new external_value(PARAM_RAW, 'Phản hồi từ FastAPI phân tích tiến độ khóa học'),
            'chartdata' => new external_single_structure([
                'good_percent'    => new external_value(PARAM_FLOAT, 'Tỷ lệ % học viên giỏi (>= 80%)'),
                'average_percent' => new external_value(PARAM_FLOAT, 'Tỷ lệ % học viên trung bình (50% - 79%)'),
                'poor_percent'    => new external_value(PARAM_FLOAT, 'Tỷ lệ % học viên yếu (< 50%)'),
                'top_names'       => new external_value(PARAM_RAW, 'Chuỗi HTML danh sách tên học viên giỏi để hiển thị tooltip'),
                'bottom_names'    => new external_value(PARAM_RAW, 'Chuỗi HTML danh sách tên học viên yếu để hiển thị tooltip')
            ])
        ]);
    }
}