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
    
    // Get movie details
    $stmt = $pdo->prepare("SELECT id, movie_title, gdflix_url, download_links, poster_url, status FROM " . DB_TABLE . " WHERE id = ?");
    $stmt->execute([$movie_id]);
    $movie = $stmt->fetch();
    
    if (!$movie) {
        throw new Exception('Movie not found');
    }
    
    // Check if movie can be triggered
    if (!in_array($movie['status'], ['pending', 'failed'])) {
        throw new Exception('Movie is already ' . $movie['status']);
    }
    
    // Get GitHub token from environment
    $env_file = PROJECT_ROOT . '/.env';
    $github_token = null;
    
    if (file_exists($env_file)) {
        $env_vars = file($env_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        foreach ($env_vars as $line) {
            if (strpos($line, 'GITHUB_TOKEN=') === 0) {
                $github_token = trim(str_replace('GITHUB_TOKEN=', '', $line));
                break;
            }
        }
    }
    
    if (!$github_token) {
        throw new Exception('GitHub token not found in .env');
    }
    
    // Prepare GitHub Actions dispatch
    $github_api_url = "https://api.github.com/repos/sajibrasel1/ftp_movie_bot/actions/workflows/process_mlsbd_movie.yml/dispatches";
    
    // Parse download_links if available
    $download_links = $movie['download_links'] ? json_decode($movie['download_links'], true) : [];
    $movie_url = $movie['gdflix_url'] ?: ($download_links['gdflix'] ?? '');
    
    $payload = [
        'ref' => 'main',
        'inputs' => [
            'movie_id' => (string)$movie['id'],
            'movie_title' => $movie['movie_title'],
            'movie_url' => $movie_url,
            'download_links' => json_encode($download_links),
            'poster_url' => $movie['poster_url'] ?? ''
        ]
    ];
    
    // Make GitHub API request
    $ch = curl_init($github_api_url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $github_token,
            'Accept: application/vnd.github.v3+json',
            'Content-Type: application/json',
            'User-Agent: MLSBD-Bot-Dashboard'
        ]
    ]);
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    
    if ($http_code !== 204) {
        throw new Exception('GitHub API returned status ' . $http_code . ': ' . $response);
    }
    
    // Update movie status to processing
    $stmt = $pdo->prepare("UPDATE " . DB_TABLE . " SET status = 'processing', updated_at = NOW() WHERE id = ?");
    $stmt->execute([$movie_id]);
    
    echo json_encode([
        'success' => true,
        'message' => 'Movie triggered successfully',
        'movie_id' => $movie_id,
        'movie_title' => $movie['movie_title']
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to trigger movie',
        'message' => $e->getMessage()
    ]);
}
