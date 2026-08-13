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

// Get POST data
$data = json_decode(file_get_contents('php://input'), true);
$log_type = $data['type'] ?? '';

// Map log types to file paths
$log_files = [
    'collect' => PROJECT_ROOT . '/logs/cron_collect.log',
    'deliver' => PROJECT_ROOT . '/logs/cron_deliver.log',
    'trigger' => PROJECT_ROOT . '/logs/mlsbd_trigger.log',
    'cron' => PROJECT_ROOT . '/logs/cron_collect.log'
];

if (!isset($log_files[$log_type])) {
    echo json_encode([
        'success' => false,
        'message' => 'Invalid log type'
    ]);
    exit;
}

$log_file = $log_files[$log_type];

try {
    if (file_exists($log_file)) {
        // Clear the log file
        file_put_contents($log_file, '');
        
        echo json_encode([
            'success' => true,
            'message' => 'Log file cleared successfully'
        ]);
    } else {
        echo json_encode([
            'success' => false,
            'message' => 'Log file not found'
        ]);
    }
} catch (Exception $e) {
    echo json_encode([
        'success' => false,
        'message' => 'Error clearing log file: ' . $e->getMessage()
    ]);
}
