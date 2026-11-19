<?php
defined('MOODLE_INTERNAL') || die();

$capabilities = array(
    'local/mychatbot:use' => [
        'captype'      => 'read',
        'contextlevel' => CONTEXT_SYSTEM,
        'archetypes'   => [
            'user' => CAP_ALLOW,
        ],
    ],
);