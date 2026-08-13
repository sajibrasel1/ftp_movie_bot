<?php
require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'error' => 'Method not allowed']);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true);
$movie_id = isset($input['movie_id']) ? intval($input['movie_id']) : 0;

if (!$movie_id) {
    http_response_code(400);
    echo json_encode(['success' => false, 'error' => 'Movie ID required']);
    exit;
}

try {
    $pdo = getDBConnection();
    
    // Check if movie exists
    $stmt = $pdo->prepare("SELECT id, movie_title FROM " . DB_TABLE . " WHERE id = ?");
    $stmt->execute([$movie_id]);
    $movie = $stmt->fetch();
    
    if (!$movie) {
        throw new Exception('Movie not found');
    }
    
    // Delete movie
    $stmt = $pdo->prepare("DELETE FROM " . DB_TABLE . " WHERE id = ?");
    $stmt->execute([$movie_id]);
    
    echo json_encode([
        'success' => true,
        'message' => 'Movie deleted successfully',
        'movie_id' => $movie_id,
        'movie_title' => $movie['movie_title']
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to delete movie',
        'message' => $e->getMessage()
    ]);
}
