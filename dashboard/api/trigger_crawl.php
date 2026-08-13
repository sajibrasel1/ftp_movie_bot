<?php
require_once '../config.php';
checkAuth();

header('Content-Type: application/json');

try {
    // Change to project directory and run trigger script
    $project_root = PROJECT_ROOT;
    $python_path = PYTHON_PATH;
    $trigger_script = PYTHON_TRIGGER;
    
    // Build command to run in background
    // Load environment variables from .env file
    $env_file = $project_root . '/.env';
    
    if (file_exists($env_file)) {
        // Read .env file and export variables
        $env_vars = file($env_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        $env_exports = [];
        foreach ($env_vars as $line) {
            if (strpos(trim($line), '#') === 0) continue; // Skip comments
            $parts = explode('=', $line, 2);
            if (count($parts) == 2) {
                $key = trim($parts[0]);
                $value = trim($parts[1]);
                $env_exports[] = "export {$key}={$value}";
            }
        }
        $env_string = implode(' && ', $env_exports);
        
        // Run script in background
        $command = "cd {$project_root} && {$env_string} && {$python_path} {$trigger_script} >> logs/manual_crawl.log 2>&1 &";
        
        // Execute command
        $output = shell_exec($command);
        $pid = shell_exec("pgrep -f mlsbd_trigger.py | tail -1");
        
        echo json_encode([
            'success' => true,
            'message' => 'Manual crawl started successfully',
            'pid' => trim($pid),
            'log_file' => 'logs/manual_crawl.log',
            'timestamp' => date('Y-m-d H:i:s')
        ]);
    } else {
        throw new Exception('.env file not found');
    }
    
} catch (Exception $e) {
    http_response_code(500);
    echo json_encode([
        'success' => false,
        'error' => 'Failed to start crawl',
        'message' => $e->getMessage()
    ]);
}
