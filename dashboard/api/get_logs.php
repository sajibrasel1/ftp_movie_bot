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
        'content' => '<div class="log-empty">Log file not found: ' . htmlspecialchars($log_file) . '</div>',
        'lines' => 0,
        'file_size' => '0 B'
    )));
}

// Get file size
$file_size = filesize($log_file);

// Read last N lines
$content = '';
$command = "tail -n " . intval($lines) . " " . escapeshellarg($log_file);
$content = shell_exec($command);

if (empty($content)) {
    $content = '<div class="log-empty">Log file is empty.</div>';
} else {
    // Colorize log content
    $content = colorizeLog($content);
}

echo json_encode(array(
    'success' => true,
    'content' => $content,
    'lines' => substr_count($content, "\n"),
    'file_size' => formatBytes($file_size),
    'last_modified' => date('Y-m-d H:i:s', filemtime($log_file))
));

function colorizeLog($content) {
    $lines = explode("\n", $content);
    $colored_lines = array();
    
    foreach ($lines as $line) {
        if (empty(trim($line))) {
            $colored_lines[] = $line;
            continue;
        }
        
        $class = 'log-line';
        
        // Detect log level
        if (preg_match('/ERROR|FAILED|Exception|Traceback/i', $line)) {
            $class .= ' log-error';
        } elseif (preg_match('/WARNING|WARN/i', $line)) {
            $class .= ' log-warning';
        } elseif (preg_match('/SUCCESS|COMPLETED|Uploaded/i', $line)) {
            $class .= ' log-success';
        } elseif (preg_match('/INFO|Starting|Processing/i', $line)) {
            $class .= ' log-info';
        }
        
        // Escape HTML
        $escaped_line = htmlspecialchars($line, ENT_QUOTES, 'UTF-8');
        
        // Highlight timestamps after escaping
        $escaped_line = preg_replace('/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/', '<span class="log-timestamp">$1</span>', $escaped_line);
        
        $colored_lines[] = '<div class="' . $class . '">' . $escaped_line . '</div>';
    }
    
    return implode('', $colored_lines);
}
