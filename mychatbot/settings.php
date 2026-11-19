<?php
defined('MOODLE_INTERNAL') || die;

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_mychatbot', get_string('pluginname', 'local_mychatbot'));
    $ADMIN->add('localplugins', $settings);

    $settings->add(new admin_setting_configtext(
        'local_mychatbot/fastapi_url',
        get_string('fastapi_url', 'local_mychatbot'),
        get_string('fastapi_url_desc', 'local_mychatbot'),
        'http://127.0.0.1:8000',
        PARAM_URL
    ));
}