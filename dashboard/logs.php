<?php
session_start();
require_once 'config.php';

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    header('Location: login.php');
    exit;
}

$page_title = 'System Logs';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $page_title; ?> - MLSBD Bot Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    <link rel="stylesheet" href="assets/css/dashboard.css">
    <style>
        .log-viewer {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 13px;
            padding: 15px;
            border-radius: 5px;
            max-height: 500px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .log-line {
            margin: 2px 0;
            padding: 2px 0;
        }
        .log-error {
            color: #f48771;
            font-weight: 500;
        }
        .log-warning {
            color: #dcdcaa;
        }
        .log-success {
            color: #4ec9b0;
        }
        .log-info {
            color: #9cdcfe;
        }
        .log-timestamp {
            color: #808080;
        }
        .log-card {
            margin-bottom: 20px;
        }
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .auto-refresh-badge {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .log-empty {
            text-align: center;
            color: #888;
            padding: 40px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
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
                        <a class="nav-link" href="movies.php">
                            <i class="bi bi-collection-play"></i> Movies
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link active" href="logs.php">
                            <i class="bi bi-file-text"></i> Logs
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

    <div class="container-fluid mt-4">
        <div class="row">
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h2><i class="bi bi-file-text"></i> System Logs</h2>
                    <div>
                        <span class="badge bg-success auto-refresh-badge" id="autoRefreshBadge">
                            <i class="bi bi-arrow-clockwise"></i> Auto-refresh: 10s
                        </span>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="toggleAutoRefresh()">
                            <i class="bi bi-pause-fill" id="refreshIcon"></i> <span id="refreshText">Pause</span>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary ms-2" onclick="refreshAllLogs()">
                            <i class="bi bi-arrow-clockwise"></i> Refresh All
                        </button>
                    </div>
                </div>

                <!-- Log File Tabs -->
                <ul class="nav nav-tabs" id="logTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="collect-tab" data-bs-toggle="tab" data-bs-target="#collect" type="button">
                            <i class="bi bi-download"></i> Collect Logs
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="deliver-tab" data-bs-toggle="tab" data-bs-target="#deliver" type="button">
                            <i class="bi bi-send"></i> Deliver Logs
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="trigger-tab" data-bs-toggle="tab" data-bs-target="#trigger" type="button">
                            <i class="bi bi-lightning"></i> Trigger Logs
                        </button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="cron-tab" data-bs-toggle="tab" data-bs-target="#cron" type="button">
                            <i class="bi bi-clock"></i> Cron Logs
                        </button>
                    </li>
                </ul>

                <!-- Tab Content -->
                <div class="tab-content mt-3" id="logTabsContent">
                    <!-- Collect Logs -->
                    <div class="tab-pane fade show active" id="collect" role="tabpanel">
                        <div class="log-card">
                            <div class="log-header">
                                <h5><i class="bi bi-file-earmark-text"></i> Collect Log (Last 100 lines)</h5>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary" onclick="downloadLog('collect')">
                                        <i class="bi bi-download"></i> Download
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="clearLog('collect')">
                                        <i class="bi bi-trash"></i> Clear
                                    </button>
                                </div>
                            </div>
                            <div class="log-viewer" id="collectLog">
                                <div class="log-empty">Loading logs...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Deliver Logs -->
                    <div class="tab-pane fade" id="deliver" role="tabpanel">
                        <div class="log-card">
                            <div class="log-header">
                                <h5><i class="bi bi-file-earmark-text"></i> Deliver Log (Last 100 lines)</h5>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary" onclick="downloadLog('deliver')">
                                        <i class="bi bi-download"></i> Download
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="clearLog('deliver')">
                                        <i class="bi bi-trash"></i> Clear
                                    </button>
                                </div>
                            </div>
                            <div class="log-viewer" id="deliverLog">
                                <div class="log-empty">Loading logs...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Trigger Logs -->
                    <div class="tab-pane fade" id="trigger" role="tabpanel">
                        <div class="log-card">
                            <div class="log-header">
                                <h5><i class="bi bi-file-earmark-text"></i> Trigger Log (Last 100 lines)</h5>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary" onclick="downloadLog('trigger')">
                                        <i class="bi bi-download"></i> Download
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="clearLog('trigger')">
                                        <i class="bi bi-trash"></i> Clear
                                    </button>
                                </div>
                            </div>
                            <div class="log-viewer" id="triggerLog">
                                <div class="log-empty">Loading logs...</div>
                            </div>
                        </div>
                    </div>

                    <!-- Cron Logs -->
                    <div class="tab-pane fade" id="cron" role="tabpanel">
                        <div class="log-card">
                            <div class="log-header">
                                <h5><i class="bi bi-file-earmark-text"></i> Cron Log (Last 100 lines)</h5>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary" onclick="downloadLog('cron')">
                                        <i class="bi bi-download"></i> Download
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger" onclick="clearLog('cron')">
                                        <i class="bi bi-trash"></i> Clear
                                    </button>
                                </div>
                            </div>
                            <div class="log-viewer" id="cronLog">
                                <div class="log-empty">Loading logs...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="assets/js/logs.js"></script>
</body>
</html>
