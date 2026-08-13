<?php
/**
 * API: Retry Failed Movies
 * Resets all failed movies to pending and optionally triggers them
 */

require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

try {
    $pdo = getDBConnection();
    
    // Get action parameter
    $action = $_POST['action'] ?? 'reset'; // 'reset' or 'trigger'
    
    // Get all failed movies
    $stmt = $pdo->query("SELECT id, movie_title FROM " . DB_TABLE . " WHERE status='failed' ORDER BY id ASC");
    $failed_movies = $stmt->fetchAll();
    
    if (empty($failed_movies)) {
        echo json_encode([
            'success' => true,
            'message' => 'No failed movies found',
            'count' => 0
        ]);
        exit;
    }
    
    // Reset failed movies to pending
    $stmt = $pdo->prepare("
        UPDATE " . DB_TABLE . " 
        SET status='pending', 
            error_message=NULL, 
            retry_count=0,
            updated_at=NOW()
        WHERE status='failed'
    ");
    $stmt->execute();
    
    $count = count($failed_movies);
    $triggered = [];
    
    // If trigger action, trigger each movie via GitHub Actions
    if ($action === 'trigger') {
        foreach ($failed_movies as $movie) {
            $movie_id = $movie['id'];
            
            // Load .env file
            $env_file = PROJECT_ROOT . '/.env';
            if (file_exists($env_file)) {
                $env_content = file_get_contents($env_file);
                preg_match('/GITHUB_TOKEN=(.+)/', $env_content, $matches);
                $github_token = $matches[1] ?? null;
                
                if ($github_token) {
                    // Trigger GitHub Action
                    $url = "https://api.github.com/repos/sajibrasel1/ftp_movie_bot/actions/workflows/process_mlsbd_movie.yml/dispatches";
                    
                    $data = json_encode([
                        'ref' => 'main',
                        'inputs' => [
                            'movie_id' => (string)$movie_id
                        ]
                    ]);
                    
                    $ch = curl_init($url);
                    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                    curl_setopt($ch, CURLOPT_POST, true);
                    curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
                    curl_setopt($ch, CURLOPT_HTTPHEADER, [
                        'Accept: application/vnd.github.v3+json',
                        'Authorization: token ' . $github_token,
                        'User-Agent: MLSBD-Bot',
                        'Content-Type: application/json'
                    ]);
                    
                    $response = curl_exec($ch);
                    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
                    curl_close($ch);
                    
                    if ($http_code === 204) {
                        $triggered[] = $movie_id;
                        
                        // Update status to processing
                        $stmt = $pdo->prepare("UPDATE " . DB_TABLE . " SET status='processing', updated_at=NOW() WHERE id=?");
                        $stmt->execute([$movie_id]);
                    }
                }
            }
            
            // Small delay between triggers
            usleep(500000); // 0.5 second
        }
    }
    
    echo json_encode([
        'success' => true,
        'message' => $action === 'trigger' 
            ? "Reset {$count} failed movies and triggered " . count($triggered) . " successfully"
            : "Reset {$count} failed movies to pending",
        'count' => $count,
        'triggered' => count($triggered),
        'movies' => $failed_movies
    ]);
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => $e->getMessage()
    ]);
}
