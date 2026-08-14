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
$isActive = $input['is_active'] ?? false;

if (!$id) {
    echo json_encode(['success' => false, 'message' => 'Missing ad ID']);
    exit;
}

try {
    $conn = get_db_connection();
    $stmt = $conn->prepare("
        UPDATE movie_ads_config 
        SET is_active = :is_active 
        WHERE id = :id
    ");
    $stmt->execute(['is_active' => $isActive ? 1 : 0, 'id' => $id]);
    
    echo json_encode(['success' => true, 'message' => 'Ad toggled']);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'Database error']);
}
