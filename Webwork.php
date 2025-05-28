<?php
/*
Plugin Name: TeraBox Downloader Proxy
Description: Acts as a proxy for TeraBox API requests
Version: 1.0
*/

add_action('rest_api_init', function() {
    register_rest_route('terabox/v1', '/download', [
        'methods' => 'GET',
        'callback' => 'handle_terabox_request',
        'permission_callback' => '__return_true'
    ]);
});

function handle_terabox_request(WP_REST_Request $request) {
    $url = $request->get_param('url');
    
    if (empty($url)) {
        return new WP_Error('missing_url', 'URL parameter is required', ['status' => 400]);
    }

    if (!preg_match('/terabox\.com|teraboxapp\.com/', $url)) {
        return new WP_Error('invalid_url', 'Invalid TeraBox URL', ['status' => 400]);
    }

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
