<?php
defined('MOODLE_INTERNAL') || die();

$messageproviders = [
    'daily_reminder' => [
        'name'             => get_string('messagename_dailyreminder', 'local_mychatbot'),
        'capability'       => 'local/mychatbot:use',
        'defaults'         => [
            'popup' => MESSAGE_PERMITTED,
            'email' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
        ],
        'supportedoutputs' => ['popup', 'email'],
    ],
];