<?php
require_once 'config.php';
checkAuth();

// Get database connection
$pdo = getDBConnection();

// Fetch statistics
$stats = [
    'total' => 0,
    'completed' => 0,
    'processing' => 0,
    'pending' => 0,
    'failed' => 0
];

try {
    // Total movies
    $stmt = $pdo->query("SELECT COUNT(*) as count FROM " . DB_TABLE);
    $stats['total'] = $stmt->fetch()['count'];
    
    // Status breakdown
    $stmt = $pdo->query("SELECT status, COUNT(*) as count FROM " . DB_TABLE . " GROUP BY status");
    while ($row = $stmt->fetch()) {
        $stats[$row['status']] = $row['count'];
    }
    
    // Recent movies
    $stmt = $pdo->query("SELECT id, movie_title, status, quality, created_at, updated_at FROM " . DB_TABLE . " ORDER BY id DESC LIMIT 10");
    $recent_movies = $stmt->fetchAll();
    
    // System info
    $stmt = $pdo->query("SELECT created_at FROM " . DB_TABLE . " ORDER BY created_at DESC LIMIT 1");
    $last_crawl = $stmt->fetch()['created_at'] ?? null;
    
} catch (PDOException $e) {
    $error = "Database error: " . $e->getMessage();
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MLSBD Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="assets/css/dashboard.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container-fluid">
            <a class="navbar-brand" href="index.php">
                <i class="bi bi-film"></i> MLSBD Bot Dashboard
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link active" href="index.php">
                            <i class="bi bi-speedometer2"></i> Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="movies.php">
                            <i class="bi bi-collection-play"></i> Movies
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="logs.php">
                            <i class="bi bi-journal-text"></i> Logs
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="logout.php">
                            <i class="bi bi-box-arrow-right"></i> Logout
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container-fluid mt-4">
        <!-- Statistics Cards -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3">
                <div class="card stat-card stat-total">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Total Movies</h6>
                                <h2 class="card-title mb-0"><?php echo $stats['total']; ?></h2>
                            </div>
                            <div class="stat-icon">
                                <i class="bi bi-film"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="card stat-card stat-completed">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Completed</h6>
                                <h2 class="card-title mb-0"><?php echo $stats['completed']; ?></h2>
                            </div>
                            <div class="stat-icon">
                                <i class="bi bi-check-circle"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="card stat-card stat-processing">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Processing</h6>
                                <h2 class="card-title mb-0"><?php echo $stats['processing']; ?></h2>
                            </div>
                            <div class="stat-icon">
                                <i class="bi bi-arrow-repeat"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-3 mb-3">
                <div class="card stat-card stat-pending">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-subtitle mb-2 text-muted">Pending</h6>
                                <h2 class="card-title mb-0"><?php echo $stats['pending']; ?></h2>
                            </div>
                            <div class="stat-icon">
                                <i class="bi bi-hourglass-split"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <i class="bi bi-lightning"></i> Quick Actions
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-success btn-lg w-100" onclick="startCrawl()">
                                    <i class="bi bi-arrow-clockwise"></i> Start Manual Crawl
                                </button>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-warning btn-lg w-100" onclick="retryFailed(false)">
                                    <i class="bi bi-arrow-repeat"></i> Retry Failed Movies
                                </button>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-danger btn-lg w-100" onclick="retryFailed(true)">
                                    <i class="bi bi-lightning-fill"></i> Retry & Trigger All
                                </button>
                            </div>
                            <div class="col-md-3 mb-2">
                                <button class="btn btn-info btn-lg w-100" onclick="refreshStats()">
                                    <i class="bi bi-arrow-clockwise"></i> Refresh Stats
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- System Status -->
        <div class="row mb-4">
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-header bg-info text-white">
                        <i class="bi bi-info-circle"></i> System Status
                    </div>
                    <div class="card-body">
                        <div class="mb-2">
                            <strong>Last Crawl:</strong> 
                            <span class="badge bg-secondary">
                                <?php echo $last_crawl ? timeAgo($last_crawl) : 'Never'; ?>
                            </span>
                        </div>
                        <div class="mb-2">
                            <strong>Cron Status:</strong> 
                            <span class="badge bg-success">Active (Hourly)</span>
                        </div>
                        <div class="mb-2">
                            <strong>Database:</strong> 
                            <span class="badge bg-success">Connected</span>
                        </div>
                        <div>
                            <strong>Auto Refresh:</strong> 
                            <span class="badge bg-primary" id="autoRefreshStatus">Enabled (30s)</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6 mb-3">
                <div class="card">
                    <div class="card-header bg-warning">
                        <i class="bi bi-exclamation-triangle"></i> Failed Movies
                    </div>
                    <div class="card-body">
                        <?php if ($stats['failed'] > 0): ?>
                            <div class="alert alert-warning mb-0">
                                <strong><?php echo $stats['failed']; ?></strong> movie(s) failed to process.
                                <button class="btn btn-sm btn-warning float-end" onclick="retryFailed()">
                                    Retry All
                                </button>
                            </div>
                        <?php else: ?>
                            <div class="alert alert-success mb-0">
                                <i class="bi bi-check-circle"></i> No failed movies!
                            </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>

        <!-- Recent Movies Table -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-dark text-white">
                        <i class="bi bi-collection-play"></i> Recent Movies
                        <a href="movies.php" class="btn btn-sm btn-light float-end">View All</a>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Title</th>
                                        <th>Quality</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($recent_movies as $movie): ?>
                                    <tr>
                                        <td><?php echo $movie['id']; ?></td>
                                        <td><?php echo htmlspecialchars(substr($movie['movie_title'], 0, 50)); ?><?php echo strlen($movie['movie_title']) > 50 ? '...' : ''; ?></td>
                                        <td><span class="badge bg-info"><?php echo $movie['quality'] ?? 'N/A'; ?></span></td>
                                        <td>
                                            <?php
                                            $statusClass = [
                                                'completed' => 'success',
                                                'processing' => 'primary',
                                                'pending' => 'warning',
                                                'failed' => 'danger'
                                            ];
                                            $class = $statusClass[$movie['status']] ?? 'secondary';
                                            ?>
                                            <span class="badge bg-<?php echo $class; ?>">
                                                <?php echo ucfirst($movie['status']); ?>
                                            </span>
                                        </td>
                                        <td><?php echo timeAgo($movie['created_at']); ?></td>
                                        <td>
                                            <?php if ($movie['status'] === 'pending' || $movie['status'] === 'failed'): ?>
                                                <button class="btn btn-sm btn-primary" onclick="triggerMovie(<?php echo $movie['id']; ?>)">
                                                    <i class="bi bi-play"></i> Trigger
                                                </button>
                                            <?php else: ?>
                                                <span class="text-muted">-</span>
                                            <?php endif; ?>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast Notifications -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="notificationToast" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="bi bi-info-circle me-2"></i>
                <strong class="me-auto">Notification</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body" id="toastMessage">
                Message here
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="assets/js/dashboard.js"></script>
</body>
</html>
