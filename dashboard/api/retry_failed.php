<?php
require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

try {
    $pdo = getDBConnection();
    
    // Get failed movies count
    $stmt = $pdo->query("SELECT COUNT(*) as count FROM " . DB_TABLE . " WHERE status = 'failed'");
    $failed_count = $stmt->fetch()['count'];
    
    if ($failed_count == 0) {
        echo json_encode([
            'success' => true,
            'message' => 'No failed movies to retry',
            'count' => 0
        ]);
        exit;
    }
    
    // Mark all failed movies as pending
    $stmt = $pdo->prepare("UPDATE " . DB_TABLE . " SET status = 'pending', error_message = NULL, updated_at = NOW() WHERE status = 'failed'");
    $stmt->execute();
    
    echo json_encode([
        'success' => true,
        'message' => $failed_count . ' movie(s) marked for retry',
        'count' => $failed_count
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to retry movies',
        'message' => $e->getMessage()
    ]);
}
