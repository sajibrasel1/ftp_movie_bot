<?php
require_once 'config.php';
checkAuth();

$pdo = getDBConnection();

// Pagination settings
$page = isset($_GET['page']) ? max(1, intval($_GET['page'])) : 1;
$limit = 20;
$offset = ($page - 1) * $limit;

// Filters
$status_filter = isset($_GET['status']) && $_GET['status'] !== 'all' ? $_GET['status'] : null;
$search = isset($_GET['search']) ? trim($_GET['search']) : null;

// Build query
$where_conditions = [];
$params = [];

if ($status_filter) {
    $where_conditions[] = "status = ?";
    $params[] = $status_filter;
}

if ($search) {
    $where_conditions[] = "(movie_title LIKE ? OR id = ?)";
    $params[] = "%{$search}%";
    $params[] = $search;
}

$where_clause = !empty($where_conditions) ? "WHERE " . implode(" AND ", $where_conditions) : "";

// Get total count
$count_query = "SELECT COUNT(*) as total FROM " . DB_TABLE . " " . $where_clause;
$stmt = $pdo->prepare($count_query);
$stmt->execute($params);
$total_movies = $stmt->fetch()['total'];
$total_pages = ceil($total_movies / $limit);

// Get movies
$movies_query = "SELECT id, movie_title, status, quality, year, is_split, total_parts, 
                        file_size, created_at, updated_at, processing_started_at, processing_completed_at, 
                        error_message, retry_count
                 FROM " . DB_TABLE . " " . $where_clause . "
                 ORDER BY id DESC LIMIT ? OFFSET ?";

$stmt = $pdo->prepare($movies_query);
foreach ($params as $key => $value) {
    $stmt->bindValue($key + 1, $value);
}
$stmt->bindValue(count($params) + 1, $limit, PDO::PARAM_INT);
$stmt->bindValue(count($params) + 2, $offset, PDO::PARAM_INT);
$stmt->execute();
$movies = $stmt->fetchAll();

// Get status counts for filter badges
$status_counts = [];
$stmt = $pdo->query("SELECT status, COUNT(*) as count FROM " . DB_TABLE . " GROUP BY status");
while ($row = $stmt->fetch()) {
    $status_counts[$row['status']] = $row['count'];
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Movies - MLSBD Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="assets/css/dashboard.css">
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
                        <a class="nav-link" href="index.php">
                            <i class="bi bi-speedometer2"></i> Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="movies.php">
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
        <div class="row mb-4">
            <div class="col-12">
                <h2><i class="bi bi-collection-play"></i> All Movies (<?php echo $total_movies; ?>)</h2>
            </div>
        </div>

        <!-- Filters and Search -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-primary text-white">
                        <i class="bi bi-funnel"></i> Filters & Search
                    </div>
                    <div class="card-body">
                        <form method="GET" action="movies.php" class="row g-3">
                            <div class="col-md-4">
                                <label for="status" class="form-label">Status</label>
                                <select name="status" id="status" class="form-select">
                                    <option value="all" <?php echo !$status_filter ? 'selected' : ''; ?>>
                                        All Statuses (<?php echo array_sum($status_counts); ?>)
                                    </option>
                                    <option value="completed" <?php echo $status_filter === 'completed' ? 'selected' : ''; ?>>
                                        ✅ Completed (<?php echo $status_counts['completed'] ?? 0; ?>)
                                    </option>
                                    <option value="processing" <?php echo $status_filter === 'processing' ? 'selected' : ''; ?>>
                                        ⏳ Processing (<?php echo $status_counts['processing'] ?? 0; ?>)
                                    </option>
                                    <option value="pending" <?php echo $status_filter === 'pending' ? 'selected' : ''; ?>>
                                        ⏰ Pending (<?php echo $status_counts['pending'] ?? 0; ?>)
                                    </option>
                                    <option value="failed" <?php echo $status_filter === 'failed' ? 'selected' : ''; ?>>
                                        ❌ Failed (<?php echo $status_counts['failed'] ?? 0; ?>)
                                    </option>
                                </select>
                            </div>
                            
                            <div class="col-md-6">
                                <label for="search" class="form-label">Search</label>
                                <input type="text" name="search" id="search" class="form-control" 
                                       placeholder="Search by title or ID..." 
                                       value="<?php echo htmlspecialchars($search ?? ''); ?>">
                            </div>
                            
                            <div class="col-md-2 d-flex align-items-end">
                                <button type="submit" class="btn btn-primary w-100">
                                    <i class="bi bi-search"></i> Filter
                                </button>
                            </div>
                        </form>
                        
                        <?php if ($status_filter || $search): ?>
                        <div class="mt-3">
                            <a href="movies.php" class="btn btn-sm btn-outline-secondary">
                                <i class="bi bi-x-circle"></i> Clear Filters
                            </a>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>

        <!-- Movies Table -->
        <div class="row">
            <div class="col-12">
                <div class="card">
                    <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                        <span><i class="bi bi-list"></i> Movies List</span>
                        <span class="badge bg-light text-dark">
                            Showing <?php echo $offset + 1; ?>-<?php echo min($offset + $limit, $total_movies); ?> of <?php echo $total_movies; ?>
                        </span>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover table-striped">
                                <thead class="table-dark">
                                    <tr>
                                        <th style="width: 60px;">ID</th>
                                        <th>Title</th>
                                        <th style="width: 100px;">Quality</th>
                                        <th style="width: 100px;">Size</th>
                                        <th style="width: 100px;">Status</th>
                                        <th style="width: 80px;">Parts</th>
                                        <th style="width: 150px;">Created</th>
                                        <th style="width: 200px;">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php if (empty($movies)): ?>
                                    <tr>
                                        <td colspan="8" class="text-center text-muted py-4">
                                            <i class="bi bi-inbox" style="font-size: 48px;"></i>
                                            <p class="mt-2">No movies found</p>
                                        </td>
                                    </tr>
                                    <?php else: ?>
                                        <?php foreach ($movies as $movie): ?>
                                        <tr>
                                            <td><strong><?php echo $movie['id']; ?></strong></td>
                                            <td>
                                                <div style="max-width: 400px; overflow: hidden; text-overflow: ellipsis;">
                                                    <?php echo htmlspecialchars($movie['movie_title']); ?>
                                                </div>
                                                <?php if ($movie['year']): ?>
                                                    <small class="text-muted">(<?php echo $movie['year']; ?>)</small>
                                                <?php endif; ?>
                                            </td>
                                            <td>
                                                <span class="badge bg-info">
                                                    <?php echo $movie['quality'] ?? 'N/A'; ?>
                                                </span>
                                            </td>
                                            <td>
                                                <?php if ($movie['file_size']): ?>
                                                    <span class="badge bg-secondary">
                                                        <?php echo formatBytes($movie['file_size']); ?>
                                                    </span>
                                                <?php else: ?>
                                                    <span class="text-muted">-</span>
                                                <?php endif; ?>
                                            </td>
                                            <td>
                                                <?php
                                                $statusConfig = [
                                                    'completed' => ['icon' => 'check-circle', 'class' => 'success'],
                                                    'processing' => ['icon' => 'arrow-repeat', 'class' => 'primary'],
                                                    'pending' => ['icon' => 'hourglass-split', 'class' => 'warning'],
                                                    'failed' => ['icon' => 'x-circle', 'class' => 'danger']
                                                ];
                                                $config = $statusConfig[$movie['status']] ?? ['icon' => 'question-circle', 'class' => 'secondary'];
                                                ?>
                                                <span class="badge bg-<?php echo $config['class']; ?>">
                                                    <i class="bi bi-<?php echo $config['icon']; ?>"></i>
                                                    <?php echo ucfirst($movie['status']); ?>
                                                </span>
                                                <?php if ($movie['retry_count'] > 0): ?>
                                                    <br><small class="text-muted">Retries: <?php echo $movie['retry_count']; ?></small>
                                                <?php endif; ?>
                                            </td>
                                            <td>
                                                <?php if ($movie['is_split']): ?>
                                                    <span class="badge bg-warning text-dark">
                                                        <?php echo $movie['total_parts']; ?> parts
                                                    </span>
                                                <?php else: ?>
                                                    <span class="badge bg-secondary">Single</span>
                                                <?php endif; ?>
                                            </td>
                                            <td>
                                                <small><?php echo timeAgo($movie['created_at']); ?></small>
                                            </td>
                                            <td>
                                                <div class="btn-group btn-group-sm" role="group">
                                                    <?php if ($movie['status'] === 'pending' || $movie['status'] === 'failed'): ?>
                                                        <button class="btn btn-primary" onclick="triggerMovie(<?php echo $movie['id']; ?>)" 
                                                                title="Trigger Processing">
                                                            <i class="bi bi-play-fill"></i>
                                                        </button>
                                                    <?php endif; ?>
                                                    
                                                    <button class="btn btn-info" onclick="viewDetails(<?php echo $movie['id']; ?>)" 
                                                            title="View Details">
                                                        <i class="bi bi-eye"></i>
                                                    </button>
                                                    
                                                    <?php if ($movie['status'] === 'failed'): ?>
                                                        <button class="btn btn-warning" onclick="retryMovie(<?php echo $movie['id']; ?>)" 
                                                                title="Retry">
                                                            <i class="bi bi-arrow-repeat"></i>
                                                        </button>
                                                    <?php endif; ?>
                                                    
                                                    <button class="btn btn-danger" onclick="deleteMovie(<?php echo $movie['id']; ?>)" 
                                                            title="Delete">
                                                        <i class="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                                
                                                <?php if ($movie['error_message']): ?>
                                                    <button class="btn btn-sm btn-outline-danger mt-1 w-100" 
                                                            onclick="showError(<?php echo $movie['id']; ?>, '<?php echo htmlspecialchars(addslashes($movie['error_message'])); ?>')"
                                                            title="View Error">
                                                        <i class="bi bi-exclamation-triangle"></i> Error
                                                    </button>
                                                <?php endif; ?>
                                            </td>
                                        </tr>
                                        <?php endforeach; ?>
                                    <?php endif; ?>
                                </tbody>
                            </table>
                        </div>
                        
                        <!-- Pagination -->
                        <?php if ($total_pages > 1): ?>
                        <nav aria-label="Page navigation" class="mt-4">
                            <ul class="pagination justify-content-center">
                                <li class="page-item <?php echo $page <= 1 ? 'disabled' : ''; ?>">
                                    <a class="page-link" href="?page=<?php echo $page - 1; ?><?php echo $status_filter ? '&status=' . $status_filter : ''; ?><?php echo $search ? '&search=' . urlencode($search) : ''; ?>">
                                        Previous
                                    </a>
                                </li>
                                
                                <?php
                                $start = max(1, $page - 2);
                                $end = min($total_pages, $page + 2);
                                
                                for ($i = $start; $i <= $end; $i++):
                                ?>
                                    <li class="page-item <?php echo $i === $page ? 'active' : ''; ?>">
                                        <a class="page-link" href="?page=<?php echo $i; ?><?php echo $status_filter ? '&status=' . $status_filter : ''; ?><?php echo $search ? '&search=' . urlencode($search) : ''; ?>">
                                            <?php echo $i; ?>
                                        </a>
                                    </li>
                                <?php endfor; ?>
                                
                                <li class="page-item <?php echo $page >= $total_pages ? 'disabled' : ''; ?>">
                                    <a class="page-link" href="?page=<?php echo $page + 1; ?><?php echo $status_filter ? '&status=' . $status_filter : ''; ?><?php echo $search ? '&search=' . urlencode($search) : ''; ?>">
                                        Next
                                    </a>
                                </li>
                            </ul>
                        </nav>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Movie Details Modal -->
    <div class="modal fade" id="detailsModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="bi bi-info-circle"></i> Movie Details</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" id="modalContent">
                    <div class="text-center">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Error Modal -->
    <div class="modal fade" id="errorModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-danger text-white">
                    <h5 class="modal-title"><i class="bi bi-exclamation-triangle"></i> Error Details</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p id="errorContent"></p>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast Notifications -->
    <div class="toast-container position-fixed bottom-0 end-0 p-3">
        <div id="notificationToast" class="toast" role="alert">
            <div class="toast-header">
                <i class="bi bi-info-circle me-2"></i>
                <strong class="me-auto">Notification</strong>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body" id="toastMessage"></div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="assets/js/dashboard.js"></script>
    <script src="assets/js/movies.js"></script>
</body>
</html>
