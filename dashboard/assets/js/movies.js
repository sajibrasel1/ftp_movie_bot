// ===================================
// MLSBD Bot Dashboard - Movies Page JavaScript
// ===================================

// Current movie being viewed
let currentMovie = null;

// Initialize movies page
document.addEventListener('DOMContentLoaded', function() {
    console.log('Movies page initialized');
});

// View movie details
function viewDetails(movieId) {
    fetch(`api/get_movie.php?id=${movieId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.movie) {
                currentMovie = data.movie;
                showMovieModal(data.movie);
            } else {
                showError(data.message || 'Failed to load movie details');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Failed to load movie details: ' + error.message);
        });
}

// Show movie details modal
function showMovieModal(movie) {
    const modalHTML = `
        <div class="modal fade" id="movieModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-film"></i> Movie Details
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <strong>ID:</strong><br>
                                <span class="text-muted">#${movie.id}</span>
                            </div>
                            <div class="col-md-6 mb-3">
                                <strong>Status:</strong><br>
                                ${getStatusBadge(movie.status)}
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <strong>Title:</strong><br>
                            <span class="text-muted">${movie.movie_title}</span>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <strong>Quality:</strong><br>
                                <span class="badge bg-info">${movie.quality || 'N/A'}</span>
                            </div>
                            <div class="col-md-6 mb-3">
                                <strong>Total Parts:</strong><br>
                                <span class="badge bg-secondary">${movie.total_parts || 0}</span>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <strong>Movie URL:</strong><br>
                            <a href="${movie.movie_url}" target="_blank" class="text-break">
                                ${movie.movie_url}
                            </a>
                        </div>
                        
                        ${movie.download_links ? `
                        <div class="mb-3">
                            <strong>Download Links:</strong><br>
                            <div class="bg-light p-2 rounded" style="max-height: 200px; overflow-y: auto;">
                                <small class="text-muted text-break">${movie.download_links}</small>
                            </div>
                        </div>
                        ` : ''}
                        
                        ${movie.error_message ? `
                        <div class="mb-3">
                            <strong>Error Message:</strong><br>
                            <div class="alert alert-danger mb-0">
                                <small>${movie.error_message}</small>
                            </div>
                        </div>
                        ` : ''}
                        
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <strong>Created:</strong><br>
                                <small class="text-muted">${movie.created_at || 'N/A'}</small>
                            </div>
                            <div class="col-md-6 mb-3">
                                <strong>Updated:</strong><br>
                                <small class="text-muted">${movie.updated_at || 'N/A'}</small>
                            </div>
                        </div>
                        
                        ${movie.telegram_message_id ? `
                        <div class="mb-3">
                            <strong>Telegram Message ID:</strong><br>
                            <span class="badge bg-info">${movie.telegram_message_id}</span>
                        </div>
                        ` : ''}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            Close
                        </button>
                        ${movie.status !== 'completed' ? `
                        <button type="button" class="btn btn-primary" onclick="triggerMovieFromModal(${movie.id})">
                            <i class="bi bi-lightning-fill"></i> Trigger
                        </button>
                        ` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Remove existing modal
    const existingModal = document.getElementById('movieModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // Add new modal
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('movieModal'));
    modal.show();
}

// Get status badge HTML
function getStatusBadge(status) {
    const badges = {
        'completed': '<span class="badge bg-success">Completed</span>',
        'processing': '<span class="badge bg-primary">Processing</span>',
        'pending': '<span class="badge bg-warning">Pending</span>',
        'failed': '<span class="badge bg-danger">Failed</span>'
    };
    
    return badges[status] || '<span class="badge bg-secondary">' + status + '</span>';
}

// Trigger movie from modal
function triggerMovieFromModal(movieId) {
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('movieModal'));
    if (modal) {
        modal.hide();
    }
    
    // Trigger movie
    triggerMovie(movieId);
}

// Trigger movie (reuse from dashboard.js)
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

// Delete movie
function deleteMovie(movieId) {
    if (!confirm('Are you sure you want to delete this movie? This action cannot be undone.')) {
        return;
    }
    
    const button = event.target;
    const originalText = button.innerHTML;
    
    // Show loading
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    
    fetch('api/delete_movie.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ movie_id: movieId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('Success', 'Movie deleted successfully!', 'success');
            
            // Refresh after 1 second
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            showToast('Error', data.message || 'Failed to delete movie', 'danger');
            button.disabled = false;
            button.innerHTML = originalText;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Error', 'Failed to delete movie: ' + error.message, 'danger');
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

// Show error message
function showError(message) {
    showToast('Error', message, 'danger');
}
