<?php
require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

try {
    $pdo = getDBConnection();
    
    // Get status counts
    $stats = [
        'total' => 0,
        'completed' => 0,
        'processing' => 0,
        'pending' => 0,
        'failed' => 0
    ];
    
    // Total
    $stmt = $pdo->query("SELECT COUNT(*) as count FROM " . DB_TABLE);
    $stats['total'] = $stmt->fetch()['count'];
    
    // By status
    $stmt = $pdo->query("SELECT status, COUNT(*) as count FROM " . DB_TABLE . " GROUP BY status");
    while ($row = $stmt->fetch()) {
        $stats[$row['status']] = $row['count'];
    }
    
    // Last crawl time
    $stmt = $pdo->query("SELECT created_at FROM " . DB_TABLE . " ORDER BY created_at DESC LIMIT 1");
    $last_crawl = $stmt->fetch()['created_at'] ?? null;
    
    // Currently processing movies
    $stmt = $pdo->query("SELECT id, movie_title FROM " . DB_TABLE . " WHERE status = 'processing' ORDER BY updated_at DESC");
    $processing_movies = $stmt->fetchAll();
    
    echo json_encode([
        'success' => true,
        'stats' => $stats,
        'last_crawl' => $last_crawl,
        'processing_movies' => $processing_movies,
        'timestamp' => date('Y-m-d H:i:s')
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to fetch statistics',
        'message' => $e->getMessage()
    ]);
}
