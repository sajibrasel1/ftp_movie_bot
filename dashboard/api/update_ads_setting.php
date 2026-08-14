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
$key = $input['key'] ?? '';
$value = $input['value'] ?? '';

if (empty($key)) {
    echo json_encode(['success' => false, 'message' => 'Missing key']);
    exit;
}

try {
    $conn = get_db_connection();
    $stmt = $conn->prepare("
        UPDATE movie_ads_settings 
        SET setting_value = :value 
        WHERE setting_key = :key
    ");
    $stmt->execute(['value' => $value, 'key' => $key]);
    
    echo json_encode(['success' => true, 'message' => 'Setting updated']);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => 'Database error']);
}
