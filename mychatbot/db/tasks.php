<?php
defined('MOODLE_INTERNAL') || die();

$tasks = [
    [
        'classname' => '\local_mychatbot\task\send_daily_reminders_1pm',
        'blocking'  => 0,    // 0 = Chạy song song, không block
        'minute'    => '0',  // Phút 0
        'hour'      => '13', // Giờ 13 (1 PM)
        'day'       => '*',  // Mỗi ngày
        'month'     => '*',  // Mỗi tháng
        'dayofweek' => '*',  // Mỗi ngày trong tuần
    ]
];