<?php
/**
 * MLSBD Bot Dashboard - Configuration
 * Simple password protection and database settings
 */

// Password protection
define('DASHBOARD_PASSWORD', '12345Sajibs6@');

// Database configuration
define('DB_HOST', 'localhost');
define('DB_USER', 'techandc_bot');
define('DB_PASS', '12345Sajibs6@');
define('DB_NAME', 'techandc_prompts');
define('DB_TABLE', 'mlsbd_movies');

// Project paths
define('PROJECT_ROOT', dirname(__DIR__));
define('LOGS_DIR', PROJECT_ROOT . '/logs');
define('PYTHON_TRIGGER', PROJECT_ROOT . '/mlsbd_trigger.py');
define('PYTHON_PATH', '/home/techandc/virtualenv/movie_bot_new/3.11/bin/python3');

// Session settings
session_start();

// Database connection function
function getDBConnection() {
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
        return $pdo;
    } catch (PDOException $e) {
        die(json_encode(['error' => 'Database connection failed']));
    }
}

// Check authentication
function checkAuth() {
    if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
        header('Location: login.php');
        exit;
    }
}

// Format bytes to readable size
function formatBytes($bytes, $precision = 2) {
    if ($bytes == 0) return '0 B';
    $units = ['B', 'KB', 'MB', 'GB', 'TB'];
    $pow = floor(($bytes ? log($bytes) : 0) / log(1024));
    $pow = min($pow, count($units) - 1);
    $bytes /= (1 << (10 * $pow));
    return round($bytes, $precision) . ' ' . $units[$pow];
}

// Time ago function
function timeAgo($datetime) {
    $timestamp = strtotime($datetime);
    $diff = time() - $timestamp;
    
    if ($diff < 60) return $diff . ' seconds ago';
    if ($diff < 3600) return floor($diff / 60) . ' minutes ago';
    if ($diff < 86400) return floor($diff / 3600) . ' hours ago';
    if ($diff < 604800) return floor($diff / 86400) . ' days ago';
    
    return date('M j, Y', $timestamp);
}
