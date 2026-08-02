<?php
/**
 * FTP Movie Bot - Database Update API
 * GitHub Actions এই API call করে database update করবে
 */

header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, X-API-Key');

// Handle preflight requests
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Simple API key authentication (supports both query param and header for LiteSpeed)
define('API_KEY', '05c20c0aa18dfbe052db939637eb87fb7c13cba62c05d474c09713eb62d24d84');

// Database credentials
define('DB_HOST', 'localhost');
define('DB_USER', 'techandc_bot');
define('DB_PASS', '12345Sajibs6@');
define('DB_NAME', 'techandc_prompts');

// Verify API key (check both query param and header)
$provided_key = '';
if (isset($_GET['api_key'])) {
    $provided_key = $_GET['api_key'];
} elseif (function_exists('getallheaders')) {
    $headers = getallheaders();
    $provided_key = isset($headers['X-API-Key']) ? $headers['X-API-Key'] : '';
}

if ($provided_key !== API_KEY) {
    http_response_code(401);
    echo json_encode(['error' => 'Unauthorized', 'debug' => 'Invalid API key']);
    exit;
}

// Only accept POST requests
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// Get request body
$input = file_get_contents('php://input');
$data = json_decode($input, true);

if (!$data) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON']);
    exit;
}

// Validate action field
if (!isset($data['action'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing action']);
    exit;
}

$action = $data['action'];

// Test action doesn't need movie_id
if ($action !== 'test' && !isset($data['movie_id'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing movie_id']);
    exit;
}

$movie_id = isset($data['movie_id']) ? intval($data['movie_id']) : 0;

// Connect to database
try {
    $pdo = new PDO(
        "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database connection failed']);
    exit;
}

// Handle different actions
try {
    switch ($action) {
        case 'test':
            // Test connection
            echo json_encode([
                'success' => true,
                'message' => 'API is working',
                'database' => 'Connected',
                'timestamp' => date('Y-m-d H:i:s')
            ]);
            break;
        
        case 'save_message_id':
            // Save single message ID
            if (!isset($data['message_id'])) {
                http_response_code(400);
                echo json_encode(['error' => 'Missing message_id']);
                exit;
            }
            
            // Get current message IDs
            $stmt = $pdo->prepare("SELECT telegram_message_ids FROM ftp_movies WHERE id = ?");
            $stmt->execute([$movie_id]);
            $row = $stmt->fetch();
            
            $message_ids = [];
            if ($row && $row['telegram_message_ids']) {
                $message_ids = json_decode($row['telegram_message_ids'], true);
            }
            
            // Add new message ID (avoid duplicates)
            $new_id = intval($data['message_id']);
            if (!in_array($new_id, $message_ids)) {
                $message_ids[] = $new_id;
            }
            
            // Update database
            $stmt = $pdo->prepare("
                UPDATE ftp_movies 
                SET telegram_message_ids = ?, 
                    updated_at = NOW() 
                WHERE id = ?
            ");
            $stmt->execute([json_encode($message_ids), $movie_id]);
            
            echo json_encode([
                'success' => true,
                'message' => 'Message ID saved',
                'total_parts' => count($message_ids)
            ]);
            break;
        
        case 'update_status':
            // Update movie status
            if (!isset($data['status'])) {
                http_response_code(400);
                echo json_encode(['error' => 'Missing status']);
                exit;
            }
            
            $status = $data['status'];
            $updates = ['status = ?'];
            $params = [$status];
            
            // Optional fields
            if (isset($data['is_split'])) {
                $updates[] = 'is_split = ?';
                $params[] = $data['is_split'] ? 1 : 0;
            }
            
            if (isset($data['total_parts'])) {
                $updates[] = 'total_parts = ?';
                $params[] = intval($data['total_parts']);
            }
            
            if (isset($data['telegram_message_ids'])) {
                $updates[] = 'telegram_message_ids = ?';
                $params[] = json_encode($data['telegram_message_ids']);
            }
            
            if (isset($data['telegram_channel_id'])) {
                $updates[] = 'telegram_channel_id = ?';
                $params[] = $data['telegram_channel_id'];
            }
            
            if (isset($data['error_message'])) {
                $updates[] = 'error_message = ?';
                $params[] = substr($data['error_message'], 0, 500);
            }
            
            // Timestamp updates
            if ($status === 'completed') {
                $updates[] = 'processing_completed_at = NOW()';
            } elseif ($status === 'processing') {
                $updates[] = 'processing_started_at = NOW()';
            }
            
            $updates[] = 'updated_at = NOW()';
            $params[] = $movie_id;
            
            $sql = "UPDATE ftp_movies SET " . implode(', ', $updates) . " WHERE id = ?";
            $stmt = $pdo->prepare($sql);
            $stmt->execute($params);
            
            echo json_encode([
                'success' => true,
                'message' => 'Status updated',
                'status' => $status
            ]);
            break;
        
        case 'get_uploaded_parts':
            // Get already uploaded message IDs
            $stmt = $pdo->prepare("SELECT telegram_message_ids FROM ftp_movies WHERE id = ?");
            $stmt->execute([$movie_id]);
            $row = $stmt->fetch();
            
            $message_ids = [];
            if ($row && $row['telegram_message_ids']) {
                $message_ids = json_decode($row['telegram_message_ids'], true);
            }
            
            echo json_encode([
                'success' => true,
                'message_ids' => $message_ids,
                'total_parts' => count($message_ids)
            ]);
            break;
        
        default:
            http_response_code(400);
            echo json_encode(['error' => 'Invalid action']);
            exit;
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['error' => 'Database error', 'details' => $e->getMessage()]);
    exit;
}
