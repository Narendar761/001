<?php
/*
Plugin Name: TeraBox Downloader with Logging
Description: Acts as a proxy for TeraBox API requests and logs searches
Version: 1.1
*/

// Create log file on activation
register_activation_hook(__FILE__, 'terabox_create_log_file');

function terabox_create_log_file() {
    $upload_dir = wp_upload_dir();
    $log_file = $upload_dir['basedir'] . '/terabox_searches.log';
    
    if (!file_exists($log_file)) {
        file_put_contents($log_file, "TeraBox Search Log\n=================\n");
        chmod($log_file, 0640);
    }
}

add_action('rest_api_init', function() {
    register_rest_route('terabox/v1', '/download', [
        'methods' => 'GET',
        'callback' => 'handle_terabox_request',
        'permission_callback' => '__return_true'
    ]);
});

function handle_terabox_request(WP_REST_Request $request) {
    $url = $request->get_param('url');
    $ip = $_SERVER['REMOTE_ADDR'];
    $timestamp = current_time('mysql');
    
    if (empty($url)) {
        return new WP_Error('missing_url', 'URL parameter is required', ['status' => 400]);
    }

    if (!preg_match('/terabox\.com|teraboxapp\.com/', $url)) {
        return new WP_Error('invalid_url', 'Invalid TeraBox URL', ['status' => 400]);
    }

    // Log the search
    log_terabox_search($url, $ip, $timestamp);

    $api_url = 'https://teraboxsmall.nkweb.workers.dev/?url=' . urlencode($url);
    
    $response = wp_remote_get($api_url, [
        'timeout' => 30,
        'sslverify' => false
    ]);

    if (is_wp_error($response)) {
        return new WP_Error('api_error', 'Failed to fetch from TeraBox API', ['status' => 502]);
    }

    $body = wp_remote_retrieve_body($response);
    $data = json_decode($body, true);

    if (json_last_error() !== JSON_ERROR_NONE) {
        return new WP_Error('invalid_json', 'Invalid response from API', ['status' => 502]);
    }

    return rest_ensure_response($data);
}

function log_terabox_search($url, $ip, $timestamp) {
    $upload_dir = wp_upload_dir();
    $log_file = $upload_dir['basedir'] . '/terabox_searches.log';
    
    $log_entry = sprintf(
        "[%s] IP: %s | URL: %s\n",
        $timestamp,
        $ip,
        $url
    );
    
    file_put_contents($log_file, $log_entry, FILE_APPEND);
    
    // Rotate log if it gets too large (optional)
    if (filesize($log_file) > 1048576) { // 1MB
        $backup_file = $upload_dir['basedir'] . '/terabox_searches_' . date('Y-m-d') . '.log';
        rename($log_file, $backup_file);
        file_put_contents($log_file, "TeraBox Search Log\n=================\n");
    }
}
