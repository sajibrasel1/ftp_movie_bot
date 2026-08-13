<?php
require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

$movie_id = isset($_GET['id']) ? intval($_GET['id']) : 0;

if (!$movie_id) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Movie ID required']);
    exit;
}

try {
    $pdo = getDBConnection();
    
    $stmt = $pdo->prepare("SELECT * FROM " . DB_TABLE . " WHERE id = ?");
    $stmt->execute([$movie_id]);
    $movie = $stmt->fetch();
    
    if (!$movie) {
        throw new Exception('Movie not found');
    }
    
    // Parse JSON fields
    if ($movie['telegram_message_ids']) {
        $movie['telegram_message_ids'] = json_decode($movie['telegram_message_ids'], true);
    }
    if ($movie['download_links']) {
        $movie['download_links'] = json_decode($movie['download_links'], true);
    }
    
    echo json_encode([
        'success' => true,
        'movie' => $movie
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to fetch movie',
        'message' => $e->getMessage()
    ]);
}
