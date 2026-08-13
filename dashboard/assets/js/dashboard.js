// ===================================
// MLSBD Bot Dashboard - Main JavaScript
// ===================================

// Auto-refresh interval (30 seconds)
let autoRefreshInterval = null;
const AUTO_REFRESH_INTERVAL = 30000;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized');
    
    // Load initial stats
    refreshStats();
    
    // Start auto-refresh
    startAutoRefresh();
});

// Start auto-refresh
function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
    }
    
    autoRefreshInterval = setInterval(() => {
        refreshStats();
    }, AUTO_REFRESH_INTERVAL);
}

// Stop auto-refresh
function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// Refresh statistics
function refreshStats() {
    fetch('api/get_stats.php')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatCards(data.stats);
                updateLastCrawlTime(data.stats.last_crawl);
            }
        })
        .catch(error => {
            console.error('Error fetching stats:', error);
        });
}

// Update stat cards
function updateStatCards(stats) {
    // Update total movies
    const totalElement = document.querySelector('.stat-card.total .stat-number');
    if (totalElement) {
        animateNumber(totalElement, stats.total || 0);
    }
    
    // Update completed
    const completedElement = document.querySelector('.stat-card.completed .stat-number');
    if (completedElement) {
        animateNumber(completedElement, stats.completed || 0);
    }
    
    // Update processing
    const processingElement = document.querySelector('.stat-card.processing .stat-number');
    if (processingElement) {
        animateNumber(processingElement, stats.processing || 0);
    }
    
    // Update pending
    const pendingElement = document.querySelector('.stat-card.pending .stat-number');
    if (pendingElement) {
        animateNumber(pendingElement, stats.pending || 0);
    }
}

// Animate number change
function animateNumber(element, newValue) {
    const currentValue = parseInt(element.textContent) || 0;
    
    if (currentValue === newValue) {
        return;
    }
    
    const step = (newValue - currentValue) / 20;
    let current = currentValue;
    
    const interval = setInterval(() => {
        current += step;
        
        if ((step > 0 && current >= newValue) || (step < 0 && current <= newValue)) {
            element.textContent = newValue;
            clearInterval(interval);
        } else {
            element.textContent = Math.round(current);
        }
    }, 50);
}

// Update last crawl time
function updateLastCrawlTime(timestamp) {
    const element = document.getElementById('lastCrawlTime');
    if (element && timestamp) {
        element.textContent = formatTimestamp(timestamp);
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) {
        return `${days} day${days > 1 ? 's' : ''} ago`;
    } else if (hours > 0) {
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else if (minutes > 0) {
        return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else {
        return 'Just now';
    }
}

// Start manual crawl
function startCrawl() {
    if (!confirm('Start manual crawl? This will scan MLSBD homepage for new movies.')) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    
    // Show loading
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting...';
    
    fetch('api/trigger_crawl.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', 'Manual crawl started successfully!', 'success');
            
            // Refresh stats after 5 seconds
            setTimeout(() => {
                refreshStats();
            }, 5000);
        } else {
            showToast('Error', data.message || 'Failed to start crawl', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error', 'Failed to start crawl: ' + error.message, 'danger');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalText;
    });
}

// Retry failed movies
function retryFailed(autoTrigger = false) {
    const actionText = autoTrigger 
        ? 'Retry and trigger all failed movies?' 
        : 'Retry all failed movies? This will mark them as pending.';
    
    if (!confirm(actionText)) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    
    // Show loading
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Processing...';
    
    const formData = new FormData();
    formData.append('action', autoTrigger ? 'trigger' : 'reset');
    
    fetch('api/retry_failed.php', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const message = autoTrigger 
                ? `${data.count} movies reset, ${data.triggered} triggered successfully!`
                : `${data.count} movies marked for retry`;
            showToast('Success', message, 'success');
            
            // Refresh stats
            setTimeout(() => {
                refreshStats();
                location.reload();
            }, 2000);
        } else {
            showToast('Error', data.error || data.message || 'Failed to retry movies', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error', 'Failed to retry movies: ' + error.message, 'danger');
    })
    .finally(() => {
        button.disabled = false;
        button.innerHTML = originalText;
    });
}

// Trigger specific movie
function triggerMovie(movieId) {
    if (!confirm('Trigger this movie for processing?')) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    
    // Show loading
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    fetch('api/trigger_movie.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ movie_id: movieId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', 'Movie triggered successfully!', 'success');
            
            // Refresh after 2 seconds
            setTimeout(() => {
                location.reload();
            }, 2000);
        } else {
            showToast('Error', data.message || 'Failed to trigger movie', 'danger');
            button.disabled = false;
            button.innerHTML = originalText;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error', 'Failed to trigger movie: ' + error.message, 'danger');
        button.disabled = false;
        button.innerHTML = originalText;
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

// Show error modal
function showError(message) {
    alert('Error: ' + message);
}

// Confirm action
function confirmAction(message) {
    return confirm(message);
}
