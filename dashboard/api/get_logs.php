<?php
session_start();
require_once '../config.php';

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => 'Unauthorized']);
    exit;
}

header('Content-Type: application/json');

$log_type = $_GET['type'] ?? 'collect';
$lines = intval($_GET['lines'] ?? 100);

// Map log types to file paths
// Note: collect/deliver logs are in promts project, not ftp_movie_bot
$log_files = [
    'collect' => '/home/techandc/movie_bot_new/promts/logs/cron_collect.log',
    'deliver' => '/home/techandc/movie_bot_new/promts/logs/cron_deliver.log',
    'trigger' => PROJECT_ROOT . '/logs/mlsbd_trigger.log',
    'cron' => PROJECT_ROOT . '/logs/cron.log'
];

if (!isset($log_files[$log_type])) {
    echo json_encode([
        'success' => false,
        'message' => 'Invalid log type'
    ]);
    exit;
}

$log_file = $log_files[$log_type];

if (!file_exists($log_file)) {
    echo json_encode([
        'success' => true,
        'content' => "Log file not found: {$log_file}\nNo logs available yet.",
        'lines' => 0,
        'file_size' => 0
    ]);
    exit;
}

// Get file size
$file_size = filesize($log_file);

// Read last N lines
$content = '';
try {
    // Use tail command if available (Unix/Linux)
    if (strtoupper(substr(PHP_OS, 0, 3)) !== 'WIN') {
        $content = shell_exec("tail -n {$lines} " . escapeshellarg($log_file));
    } else {
        // For Windows, read file and get last lines
        $file_content = file($log_file);
        if ($file_content !== false) {
            $file_content = array_slice($file_content, -$lines);
            $content = implode('', $file_content);
        }
    }
    
    if (empty($content)) {
        $content = "Log file is empty.";
    }
    
    // Add color coding
    $content = colorizeLog($content);
    
    echo json_encode([
        'success' => true,
        'content' => $content,
        'lines' => substr_count($content, "\n"),
        'file_size' => formatBytes($file_size),
        'last_modified' => date('Y-m-d H:i:s', filemtime($log_file))
    ]);
    
} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'message' => 'Error reading log file: ' . $e->getMessage()
    ]);
}

function colorizeLog($content) {
    $lines = explode("\n", $content);
    $colored_lines = [];
    
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
        
        // Highlight timestamps
        $line = preg_replace('/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/', '<span class="log-timestamp">$1</span>', $line);
        
        $colored_lines[] = '<div class="' . $class . '">' . htmlspecialchars($line, ENT_QUOTES, 'UTF-8') . '</div>';
    }
    
    return implode('', $colored_lines);
}

function formatBytes($bytes, $precision = 2) {
    $units = ['B', 'KB', 'MB', 'GB'];
    $bytes = max($bytes, 0);
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= pow(1024, $pow);
    return round($bytes, $precision) . ' ' . $units[$pow];
}
