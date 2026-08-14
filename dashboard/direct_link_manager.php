<?php
/**
 * Direct Link Ads Manager
 * Manage redirect ads for clickable buttons
 */

// Dashboard auth first
require_once __DIR__ . '/config.php';
checkAuth();

// Then movie config for DB functions
require_once __DIR__ . '/../../movies/direct_link_helper.php';

// Handle form submissions
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';
    
    if ($action === 'add') {
        $conn = getDBConnection();
        $stmt = $conn->prepare("
            INSERT INTO direct_link_ads (ad_name, ad_network, redirect_url, display_priority)
            VALUES (:name, :network, :url, :priority)
        ");
        $stmt->execute([
            'name' => $_POST['ad_name'],
            'network' => $_POST['ad_network'],
            'url' => $_POST['redirect_url'],
            'priority' => intval($_POST['display_priority'] ?? 10)
        ]);
        $success = "Ad added successfully!";
    }
    
    elseif ($action === 'toggle') {
        $conn = getDBConnection();
        $stmt = $conn->prepare("
            UPDATE direct_link_ads 
            SET is_active = NOT is_active 
            WHERE id = :id
        ");
        $stmt->execute(['id' => $_POST['ad_id']]);
        $success = "Ad status updated!";
    }
    
    elseif ($action === 'delete') {
        $conn = getDBConnection();
        $stmt = $conn->prepare("DELETE FROM direct_link_ads WHERE id = :id");
        $stmt->execute(['id' => $_POST['ad_id']]);
        $success = "Ad deleted!";
    }
    
    elseif ($action === 'update_settings') {
        $conn = getDBConnection();
        
        $stmt = $conn->prepare("
            UPDATE movie_ads_settings 
            SET setting_value = :value 
            WHERE setting_key = 'direct_link_enabled'
        ");
        $stmt->execute(['value' => isset($_POST['direct_link_enabled']) ? '1' : '0']);
        
        $stmt = $conn->prepare("
            UPDATE movie_ads_settings 
            SET setting_value = :value 
            WHERE setting_key = 'direct_link_rotation'
        ");
        $stmt->execute(['value' => $_POST['direct_link_rotation']]);
        
        $success = "Settings updated!";
    }
}

// Get all ads
$ads = getAllDirectLinkAds();

// Get settings
$conn = getDBConnection();
$stmt = $conn->prepare("SELECT * FROM movie_ads_settings WHERE setting_key LIKE 'direct_link%'");
$stmt->execute();
$settings = [];
foreach ($stmt->fetchAll() as $row) {
    $settings[$row['setting_key']] = $row['setting_value'];
}

// Calculate total stats
$totalClicks = 0;
$totalTodayClicks = 0;
foreach ($ads as $ad) {
    $totalClicks += $ad['click_count'];
    $totalTodayClicks += $ad['today_clicks'] ?? 0;
}

// Get hourly clicks for today
$stmt = $conn->prepare("
    SELECT HOUR(clicked_at) as hour, COUNT(*) as clicks
    FROM ad_click_logs
    WHERE DATE(clicked_at) = CURDATE()
    GROUP BY HOUR(clicked_at)
    ORDER BY hour
");
$stmt->execute();
$hourlyClicks = $stmt->fetchAll();

// Get clicks by context today
$stmt = $conn->prepare("
    SELECT context, COUNT(*) as clicks
    FROM ad_click_logs
    WHERE DATE(clicked_at) = CURDATE()
    GROUP BY context
    ORDER BY clicks DESC
");
$stmt->execute();
$contextClicks = $stmt->fetchAll();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Direct Link Ads Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0f0f0f;
            color: #fff;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        h1 {
            margin-bottom: 30px;
            color: #E50914;
        }
        
        .success {
            background: #10b981;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .section {
            background: rgba(255,255,255,0.05);
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 25px;
        }
        
        .section h2 {
            margin-bottom: 20px;
            font-size: 1.5rem;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #B3B3B3;
        }
        
        input[type="text"],
        input[type="number"],
        select {
            width: 100%;
            padding: 12px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            color: #fff;
            font-size: 1rem;
        }
        
        button {
            background: #E50914;
            color: #fff;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
            transition: background 0.3s ease;
        }
        
        button:hover {
            background: #b8070f;
        }
        
        button.secondary {
            background: #555;
        }
        
        button.secondary:hover {
            background: #777;
        }
        
        button.danger {
            background: #dc2626;
        }
        
        button.danger:hover {
            background: #991b1b;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.05);
            padding: 25px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            border-color: rgba(229, 9, 20, 0.3);
        }
        
        .stat-icon {
            width: 70px;
            height: 70px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .stat-content h3 {
            font-size: 2rem;
            color: #fff;
            margin-bottom: 5px;
        }
        
        .stat-content p {
            color: #999;
            font-size: 0.9rem;
            margin: 0;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        th {
            background: rgba(229, 9, 20, 0.1);
            color: #E50914;
        }
        
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        
        .status.active {
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }
        
        .status.inactive {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }
        
        .actions {
            display: flex;
            gap: 10px;
        }
        
        .actions button {
            padding: 8px 16px;
            font-size: 0.9rem;
        }
        
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Direct Link Ads Manager</h1>
        
        <!-- Navbar -->
        <div style="margin-bottom: 25px;">
            <a href="index.php" style="color: #B3B3B3; text-decoration: none; margin-right: 20px;">
                <i class="fas fa-home"></i> Dashboard
            </a>
            <a href="ads_manager.php" style="color: #B3B3B3; text-decoration: none; margin-right: 20px;">
                <i class="fas fa-ad"></i> Ads Manager
            </a>
            <a href="direct_link_manager.php" style="color: #E50914; text-decoration: none; margin-right: 20px;">
                <i class="fas fa-link"></i> Direct Links
            </a>
            <a href="logout.php" style="color: #B3B3B3; text-decoration: none; float: right;">
                <i class="fas fa-sign-out-alt"></i> Logout
            </a>
        </div>
        
        <?php if (isset($success)): ?>
            <div class="success"><?php echo $success; ?></div>
        <?php endif; ?>
        
        <!-- Statistics Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(229, 9, 20, 0.2);">
                    <i class="fas fa-mouse-pointer" style="color: #E50914; font-size: 2rem;"></i>
                </div>
                <div class="stat-content">
                    <h3><?php echo number_format($totalClicks); ?></h3>
                    <p>Total Clicks (All Time)</p>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(16, 185, 129, 0.2);">
                    <i class="fas fa-calendar-day" style="color: #10b981; font-size: 2rem;"></i>
                </div>
                <div class="stat-content">
                    <h3><?php echo number_format($totalTodayClicks); ?></h3>
                    <p>Today's Clicks</p>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(59, 130, 246, 0.2);">
                    <i class="fas fa-ad" style="color: #3b82f6; font-size: 2rem;"></i>
                </div>
                <div class="stat-content">
                    <h3><?php echo count($ads); ?></h3>
                    <p>Active Ads</p>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: rgba(251, 191, 36, 0.2);">
                    <i class="fas fa-chart-line" style="color: #fbbf24; font-size: 2rem;"></i>
                </div>
                <div class="stat-content">
                    <h3><?php echo $totalTodayClicks > 0 && count($ads) > 0 ? number_format($totalTodayClicks / count($ads), 1) : '0'; ?></h3>
                    <p>Avg Clicks per Ad Today</p>
                </div>
            </div>
        </div>
        
        <!-- Settings -->
        <div class="section">
            <h2>⚙️ Settings</h2>
            <form method="POST">
                <input type="hidden" name="action" value="update_settings">
                
                <div class="form-group checkbox-group">
                    <input type="checkbox" 
                           name="direct_link_enabled" 
                           id="direct_link_enabled" 
                           <?php echo ($settings['direct_link_enabled'] ?? '1') == '1' ? 'checked' : ''; ?>>
                    <label for="direct_link_enabled" style="margin: 0;">Enable Direct Link Ads</label>
                </div>
                
                <div class="form-group">
                    <label>Rotation Strategy</label>
                    <select name="direct_link_rotation">
                        <option value="random" <?php echo ($settings['direct_link_rotation'] ?? 'random') == 'random' ? 'selected' : ''; ?>>Random</option>
                        <option value="priority" <?php echo ($settings['direct_link_rotation'] ?? 'random') == 'priority' ? 'selected' : ''; ?>>Priority-based</option>
                    </select>
                </div>
                
                <button type="submit">Save Settings</button>
            </form>
        </div>
        
        <!-- Add New Ad -->
        <div class="section">
            <h2>➕ Add New Direct Link Ad</h2>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                
                <div class="form-group">
                    <label>Ad Name</label>
                    <input type="text" name="ad_name" placeholder="e.g., Adsterra Direct Link" required>
                </div>
                
                <div class="form-group">
                    <label>Ad Network</label>
                    <select name="ad_network" required>
                        <option value="adsterra">Adsterra</option>
                        <option value="monetag">Monetag</option>
                        <option value="other">Other</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>Redirect URL</label>
                    <input type="text" name="redirect_url" placeholder="https://..." required>
                </div>
                
                <div class="form-group">
                    <label>Display Priority (higher = more frequent)</label>
                    <input type="number" name="display_priority" value="10" min="0" max="100">
                </div>
                
                <button type="submit">Add Ad</button>
            </form>
        </div>
        
        <!-- Existing Ads -->
        <div class="section">
            <h2>📋 Your Direct Link Ads</h2>
            
            <?php if (empty($ads)): ?>
                <p style="color: #999;">No ads configured yet.</p>
            <?php else: ?>
                <table>
                    <thead>
                        <tr>
                            <th>Ad Name</th>
                            <th>Network</th>
                            <th>Redirect URL</th>
                            <th>Priority</th>
                            <th>Today's Clicks</th>
                            <th>Total Clicks</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($ads as $ad): ?>
                            <tr>
                                <td><?php echo htmlspecialchars($ad['ad_name']); ?></td>
                                <td><?php echo htmlspecialchars($ad['ad_network']); ?></td>
                                <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">
                                    <?php echo htmlspecialchars($ad['redirect_url']); ?>
                                </td>
                                <td><?php echo $ad['display_priority']; ?></td>
                                <td>
                                    <strong style="color: #10b981;"><?php echo number_format($ad['today_clicks'] ?? 0); ?></strong>
                                </td>
                                <td><?php echo number_format($ad['click_count']); ?></td>
                                <td>
                                    <span class="status <?php echo $ad['is_active'] ? 'active' : 'inactive'; ?>">
                                        <?php echo $ad['is_active'] ? 'Active' : 'Inactive'; ?>
                                    </span>
                                </td>
                                <td>
                                    <div class="actions">
                                        <form method="POST" style="display: inline;">
                                            <input type="hidden" name="action" value="toggle">
                                            <input type="hidden" name="ad_id" value="<?php echo $ad['id']; ?>">
                                            <button type="submit" class="secondary">
                                                <?php echo $ad['is_active'] ? 'Disable' : 'Enable'; ?>
                                            </button>
                                        </form>
                                        
                                        <form method="POST" style="display: inline;" onsubmit="return confirm('Delete this ad?');">
                                            <input type="hidden" name="action" value="delete">
                                            <input type="hidden" name="ad_id" value="<?php echo $ad['id']; ?>">
                                            <button type="submit" class="danger">Delete</button>
                                        </form>
                                    </div>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
        
        <!-- Today's Click Activity -->
        <?php if (!empty($hourlyClicks)): ?>
        <div class="section">
            <h2>📈 Today's Click Activity (by Hour)</h2>
            <div style="display: flex; align-items: flex-end; gap: 10px; height: 200px; margin-top: 20px;">
                <?php 
                $maxClicks = max(array_column($hourlyClicks, 'clicks'));
                for ($h = 0; $h < 24; $h++): 
                    $clicks = 0;
                    foreach ($hourlyClicks as $hc) {
                        if ($hc['hour'] == $h) {
                            $clicks = $hc['clicks'];
                            break;
                        }
                    }
                    $height = $maxClicks > 0 ? ($clicks / $maxClicks) * 180 : 0;
                ?>
                    <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 5px;">
                        <div style="
                            width: 100%;
                            height: <?php echo $height; ?>px;
                            background: <?php echo $clicks > 0 ? '#E50914' : 'rgba(255,255,255,0.1)'; ?>;
                            border-radius: 4px 4px 0 0;
                            transition: all 0.3s ease;
                            position: relative;
                        " title="<?php echo $clicks; ?> clicks at <?php echo $h; ?>:00">
                            <?php if ($clicks > 0): ?>
                                <span style="
                                    position: absolute;
                                    top: -20px;
                                    left: 50%;
                                    transform: translateX(-50%);
                                    font-size: 0.7rem;
                                    color: #10b981;
                                    font-weight: 600;
                                "><?php echo $clicks; ?></span>
                            <?php endif; ?>
                        </div>
                        <span style="font-size: 0.7rem; color: #666;"><?php echo str_pad($h, 2, '0', STR_PAD_LEFT); ?></span>
                    </div>
                <?php endfor; ?>
            </div>
        </div>
        <?php endif; ?>
        
        <!-- Click Context Distribution -->
        <?php if (!empty($contextClicks)): ?>
        <div class="section">
            <h2>📊 Clicks by Source (Today)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Source</th>
                        <th>Clicks</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    <?php 
                    $totalContextClicks = array_sum(array_column($contextClicks, 'clicks'));
                    foreach ($contextClicks as $cc): 
                        $percentage = $totalContextClicks > 0 ? ($cc['clicks'] / $totalContextClicks) * 100 : 0;
                    ?>
                        <tr>
                            <td><?php echo htmlspecialchars($cc['context']); ?></td>
                            <td><?php echo number_format($cc['clicks']); ?></td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <div style="
                                        flex: 1;
                                        height: 8px;
                                        background: rgba(255,255,255,0.1);
                                        border-radius: 4px;
                                        overflow: hidden;
                                    ">
                                        <div style="
                                            width: <?php echo $percentage; ?>%;
                                            height: 100%;
                                            background: #E50914;
                                        "></div>
                                    </div>
                                    <span><?php echo number_format($percentage, 1); ?>%</span>
                                </div>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <?php endif; ?>
        
        <p style="text-align: center; color: #666; margin-top: 40px;">
            <a href="../index.php" style="color: #E50914; text-decoration: none;">← Back to Dashboard</a>
        </p>
    </div>
</body>
</html>
