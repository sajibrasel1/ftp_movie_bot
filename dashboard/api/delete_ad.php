<?php
session_start();
require_once '../config.php';

header('Content-Type: application/json');

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => 'Unauthorized']);
    exit;
}

// Get input
$input = json_decode(file_get_contents('php://input'), true);
$id = $input['id'] ?? 0;

if (!$id) {
    echo json_encode(['success' => false, 'message' => 'Missing ad ID']);
    exit;
}

try {
    $conn = get_db_connection();
    $stmt = $conn->prepare("DELETE FROM movie_ads_config WHERE id = :id");
    $stmt->execute(['id' => $id]);
    
    echo json_encode(['success' => true, 'message' => 'Ad deleted']);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'Database error']);
}
