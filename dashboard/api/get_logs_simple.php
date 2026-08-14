<?php
session_start();
require_once '../config.php';

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    http_response_code(401);
    die(json_encode(['success' => false, 'message' => 'Unauthorized']));
}

header('Content-Type: application/json');

$log_type = isset($_GET['type']) ? $_GET['type'] : 'collect';
$lines = isset($_GET['lines']) ? intval($_GET['lines']) : 100;

// Map log types to file paths
$log_files = array(
    'collect' => '/home/techandc/movie_bot_new/promts/logs/cron_collect.log',
    'deliver' => '/home/techandc/movie_bot_new/promts/logs/cron_deliver.log',
    'trigger' => PROJECT_ROOT . '/logs/mlsbd_trigger.log',
    'cron' => PROJECT_ROOT . '/logs/cron.log'
);

if (!isset($log_files[$log_type])) {
    die(json_encode(array('success' => false, 'message' => 'Invalid log type')));
}

$log_file = $log_files[$log_type];

if (!file_exists($log_file)) {
    die(json_encode(array(
        'success' => true,
        'content' => '<div class="log-empty">Log file not found: ' . $log_file . '</div>',
        'lines' => 0,
        'file_size' => '0 B'
    )));
}

// Get file size
$file_size = filesize($log_file);

// Read last N lines using tail
$content = shell_exec("tail -n " . escapeshellarg($lines) . " " . escapeshellarg($log_file));

if (empty($content)) {
    $content = '<div class="log-empty">Log file is empty.</div>';
} else {
    // Simple HTML formatting
    $content = '<pre>' . htmlspecialchars($content) . '</pre>';
}

echo json_encode(array(
    'success' => true,
    'content' => $content,
    'lines' => substr_count($content, "\n"),
    'file_size' => formatBytes($file_size),
    'last_modified' => date('Y-m-d H:i:s', filemtime($log_file))
));

function formatBytes($bytes) {
    $units = array('B', 'KB', 'MB', 'GB');
    $bytes = max($bytes, 0);
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= pow(1024, $pow);
    return round($bytes, 2) . ' ' . $units[$pow];
}
