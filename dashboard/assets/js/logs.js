// ===================================
// MLSBD Bot Dashboard - Logs Page JavaScript
// ===================================

// Auto-refresh settings
let autoRefreshEnabled = true;
let autoRefreshInterval = null;
const REFRESH_INTERVAL = 10000; // 10 seconds

// Current active tab
let currentTab = 'collect';

// Initialize logs page
document.addEventListener('DOMContentLoaded', function() {
    console.log('Logs page initialized');
    
    // Load initial logs
    loadLog('collect');
    
    // Start auto-refresh
    startAutoRefresh();
    
    // Tab change event
    document.querySelectorAll('#logTabs button').forEach(button => {
        button.addEventListener('shown.bs.tab', function (event) {
            currentTab = event.target.dataset.bsTarget.replace('#', '');
            loadLog(currentTab);
        });
    });
});

// Start auto-refresh
function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        if (autoRefreshEnabled) {
            loadLog(currentTab);
        }
    }, REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Toggle auto-refresh
function toggleAutoRefresh() {
    autoRefreshEnabled = !autoRefreshEnabled;
    
    const badge = document.getElementById('autoRefreshBadge');
    const icon = document.getElementById('refreshIcon');
    const text = document.getElementById('refreshText');
    
    if (autoRefreshEnabled) {
        badge.classList.remove('bg-secondary');
        badge.classList.add('bg-success', 'auto-refresh-badge');
        icon.classList.remove('bi-play-fill');
        icon.classList.add('bi-pause-fill');
        text.textContent = 'Pause';
        
        // Resume refresh
        startAutoRefresh();
        loadLog(currentTab);
    } else {
        badge.classList.remove('bg-success', 'auto-refresh-badge');
        badge.classList.add('bg-secondary');
        icon.classList.remove('bi-pause-fill');
        icon.classList.add('bi-play-fill');
        text.textContent = 'Resume';
    }
}

// Refresh all logs
function refreshAllLogs() {
    loadLog(currentTab);
    showToast('Success', 'Logs refreshed', 'success');
}

// Load log file
function loadLog(type) {
    const logContainer = document.getElementById(type + 'Log');
    
    if (!logContainer) {
        console.error('Log container not found:', type);
        return;
    }
    
    fetch(`api/get_logs.php?type=${type}&lines=100`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.content && data.content.trim()) {
                    logContainer.innerHTML = data.content;
                    
                    // Scroll to bottom
                    logContainer.scrollTop = logContainer.scrollHeight;
                } else {
                    logContainer.innerHTML = '<div class="log-empty">No logs available</div>';
                }
            } else {
                logContainer.innerHTML = `<div class="log-empty">Error: ${data.message}</div>`;
            }
        })
        .catch(error => {
            console.error('Error loading logs:', error);
            logContainer.innerHTML = `<div class="log-empty">Error loading logs: ${error.message}</div>`;
        });
}

// Download log file
function downloadLog(type) {
    // Create download link
    const link = document.createElement('a');
    link.href = `api/get_logs.php?type=${type}&lines=10000&download=1`;
    link.download = `${type}_log_${Date.now()}.txt`;
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('Success', 'Downloading log file...', 'success');
}

// Clear log file
function clearLog(type) {
    if (!confirm(`Clear ${type} log file? This action cannot be undone.`)) {
        return;
    }
    
    fetch('api/clear_log.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ type: type })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', 'Log file cleared successfully', 'success');
            
            // Reload log
            setTimeout(() => {
                loadLog(type);
            }, 500);
        } else {
            showToast('Error', data.message || 'Failed to clear log file', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error', 'Failed to clear log file: ' + error.message, 'danger');
    });
}

// Show toast notification
function showToast(title, message, type = 'info') {
    // Create toast container if not exists
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    // Create toast
    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'success' ? 'bg-success' : type === 'danger' ? 'bg-danger' : 'bg-info';
    
    const toastHTML = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header ${bgClass} text-white">
                <strong class="me-auto">${title}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: 5000
    });
    
    toast.show();
    
    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', function () {
        toastElement.remove();
    });
}
