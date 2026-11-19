<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    [
        'eventname' => '\core\event\user_created',
        'callback'  => '\local_mychatbot\event\observer\user_created::execute',
    ],
    [
        'eventname' => '\core\event\user_deleted',
        'callback'  => '\local_mychatbot\event\observer\user_deleted::execute',
    ],
    [
        'eventname' => '\mod_quiz\event\attempt_submitted',
        'callback'  => '\local_mychatbot\event\observer\attempt_submitted::execute',
    ],
    [
        'eventname' => '\core\event\course_module_created',
        'callback'  => '\local_mychatbot\event\observer\course_module_created::execute',
    ],
    [
        'eventname' => '\core\event\course_module_updated',
        'callback'  => '\local_mychatbot\event\observer\course_module_updated::execute',
    ],
];