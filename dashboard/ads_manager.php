<?php
session_start();
require_once 'config.php';

// Check authentication
if (!isset($_SESSION['authenticated']) || $_SESSION['authenticated'] !== true) {
    header('Location: login.php');
    exit;
}

// Get all ads
$ads = [];
$settings = [];

try {
    $conn = get_db_connection();
    
    // Get ads
    $stmt = $conn->query("
        SELECT * FROM movie_ads_config 
        ORDER BY priority DESC, id ASC
    ");
    $ads = $stmt->fetchAll(PDO::FETCH_ASSOC);
    
    // Get settings
    $stmt = $conn->query("SELECT * FROM movie_ads_settings");
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $settings[$row['setting_key']] = $row['setting_value'];
    }
} catch (PDOException $e) {
    $error = "Database error: " . $e->getMessage();
}

$page_title = "Ads Manager";
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo $page_title; ?> - Dashboard</title>
    <link rel="stylesheet" href="assets/css/dashboard.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .ads-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
        }
        
        .master-switch {
            background: #2F2F2F;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
        }
        
        .master-switch h3 {
            margin-bottom: 15px;
            color: #E50914;
        }
        
        .settings-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .setting-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: #1a1a1a;
            border-radius: 5px;
        }
        
        .ads-grid {
            display: grid;
            gap: 20px;
        }
        
        .ad-card {
            background: #2F2F2F;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #E50914;
        }
        
        .ad-card.inactive {
            opacity: 0.6;
            border-left-color: #666;
        }
        
        .ad-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .ad-title {
            font-size: 1.2rem;
            font-weight: 600;
            color: #fff;
        }
        
        .ad-badge {
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .badge-adsterra { background: #FF6B6B; }
        .badge-monetag { background: #4ECDC4; }
        .badge-adsense { background: #4285F4; }
        .badge-custom { background: #95E1D3; }
        
        .ad-meta {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            color: #B3B3B3;
        }
        
        .ad-code {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 150px;
            overflow-y: auto;
            margin: 15px 0;
        }
        
        .ad-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        .toggle-switch {
            position: relative;
            width: 60px;
            height: 30px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 30px;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 22px;
            width: 22px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        
        input:checked + .slider {
            background-color: #E50914;
        }
        
        input:checked + .slider:before {
            transform: translateX(30px);
        }
    </style>
</head>
<body>
    <?php include 'includes/sidebar.php'; ?>
    
    <div class="main-content">
        <?php include 'includes/header.php'; ?>
        
        <div class="content-wrapper">
            <div class="ads-header">
                <h1><i class="fas fa-ad"></i> Ads Manager</h1>
                <button class="btn btn-primary" onclick="addNewAd()">
                    <i class="fas fa-plus"></i> Add New Ad
                </button>
            </div>
            
            <?php if (isset($error)): ?>
                <div class="alert alert-danger"><?php echo $error; ?></div>
            <?php endif; ?>
            
            <!-- Master Settings -->
            <div class="master-switch">
                <h3><i class="fas fa-toggle-on"></i> Global Ads Settings</h3>
                <div class="settings-grid">
                    <div class="setting-item">
                        <span>Master Switch (All Ads)</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="ads_enabled" 
                                   <?php echo ($settings['ads_enabled'] ?? '1') == '1' ? 'checked' : ''; ?>
                                   onchange="toggleSetting('ads_enabled', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <span>Adsterra Ads</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="adsterra_enabled" 
                                   <?php echo ($settings['adsterra_enabled'] ?? '1') == '1' ? 'checked' : ''; ?>
                                   onchange="toggleSetting('adsterra_enabled', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <span>Monetag Ads</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="monetag_enabled" 
                                   <?php echo ($settings['monetag_enabled'] ?? '1') == '1' ? 'checked' : ''; ?>
                                   onchange="toggleSetting('monetag_enabled', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <span>Google AdSense</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="adsense_enabled" 
                                   <?php echo ($settings['adsense_enabled'] ?? '1') == '1' ? 'checked' : ''; ?>
                                   onchange="toggleSetting('adsense_enabled', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="setting-item">
                        <span>Show on Mobile</span>
                        <label class="toggle-switch">
                            <input type="checkbox" id="ads_on_mobile" 
                                   <?php echo ($settings['ads_on_mobile'] ?? '1') == '1' ? 'checked' : ''; ?>
                                   onchange="toggleSetting('ads_on_mobile', this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                </div>
            </div>
            
            <!-- Ads List -->
            <div class="ads-grid">
                <?php foreach ($ads as $ad): ?>
                <div class="ad-card <?php echo $ad['is_active'] ? '' : 'inactive'; ?>" id="ad-<?php echo $ad['id']; ?>">
                    <div class="ad-header">
                        <div>
                            <div class="ad-title"><?php echo htmlspecialchars($ad['ad_name']); ?></div>
                            <span class="ad-badge badge-<?php echo $ad['ad_network']; ?>">
                                <?php echo strtoupper($ad['ad_network']); ?>
                            </span>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" 
                                   <?php echo $ad['is_active'] ? 'checked' : ''; ?>
                                   onchange="toggleAd(<?php echo $ad['id']; ?>, this.checked)">
                            <span class="slider"></span>
                        </label>
                    </div>
                    
                    <div class="ad-meta">
                        <span><i class="fas fa-map-marker-alt"></i> <?php echo ucfirst(str_replace('_', ' ', $ad['placement'])); ?></span>
                        <span><i class="fas fa-tag"></i> <?php echo ucfirst($ad['ad_type']); ?></span>
                        <span><i class="fas fa-eye"></i> <?php echo number_format($ad['impressions']); ?> impressions</span>
                    </div>
                    
                    <div style="display: flex; gap: 10px; font-size: 0.85rem; color: #B3B3B3;">
                        <span><i class="fas fa-home"></i> Homepage: <?php echo $ad['display_on_homepage'] ? '✅' : '❌'; ?></span>
                        <span><i class="fas fa-film"></i> Movie Page: <?php echo $ad['display_on_movie_page'] ? '✅' : '❌'; ?></span>
                        <span><i class="fas fa-search"></i> Search: <?php echo $ad['display_on_search_page'] ? '✅' : '❌'; ?></span>
                    </div>
                    
                    <div class="ad-code">
                        <?php echo htmlspecialchars($ad['ad_code']); ?>
                    </div>
                    
                    <div class="ad-actions">
                        <button class="btn btn-sm btn-primary" onclick="editAd(<?php echo $ad['id']; ?>)">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="duplicateAd(<?php echo $ad['id']; ?>)">
                            <i class="fas fa-copy"></i> Duplicate
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteAd(<?php echo $ad['id']; ?>)">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </div>
    
    <script>
        function toggleSetting(key, value) {
            fetch('api/update_ads_setting.php', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({key: key, value: value ? '1' : '0'})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showToast('Setting updated successfully', 'success');
                } else {
                    showToast('Failed to update setting', 'error');
                }
            });
        }
        
        function toggleAd(id, isActive) {
            fetch('api/toggle_ad.php', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: id, is_active: isActive})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const card = document.getElementById('ad-' + id);
                    card.classList.toggle('inactive', !isActive);
                    showToast('Ad ' + (isActive ? 'enabled' : 'disabled'), 'success');
                } else {
                    showToast('Failed to toggle ad', 'error');
                }
            });
        }
        
        function editAd(id) {
            window.location.href = 'edit_ad.php?id=' + id;
        }
        
        function addNewAd() {
            window.location.href = 'add_ad.php';
        }
        
        function duplicateAd(id) {
            if (confirm('Duplicate this ad?')) {
                fetch('api/duplicate_ad.php', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        showToast('Ad duplicated successfully', 'success');
                        location.reload();
                    } else {
                        showToast('Failed to duplicate ad', 'error');
                    }
                });
            }
        }
        
        function deleteAd(id) {
            if (confirm('Delete this ad? This action cannot be undone.')) {
                fetch('api/delete_ad.php', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: id})
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('ad-' + id).remove();
                        showToast('Ad deleted successfully', 'success');
                    } else {
                        showToast('Failed to delete ad', 'error');
                    }
                });
            }
        }
        
        function showToast(message, type) {
            // Simple toast notification
            const toast = document.createElement('div');
            toast.className = 'toast toast-' + type;
            toast.textContent = message;
            toast.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 25px;
                background: ${type === 'success' ? '#10b981' : '#ef4444'};
                color: white;
                border-radius: 8px;
                z-index: 9999;
            `;
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
    </script>
</body>
</html>
