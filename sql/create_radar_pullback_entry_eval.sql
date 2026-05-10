CREATE TABLE IF NOT EXISTS radar_pullback_entry_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    radar_threshold_pct DOUBLE NOT NULL,
    pullback_depth_pct DOUBLE NOT NULL,
    max_pullback_bars INT NOT NULL,
    volume_shrink_ratio DOUBLE NOT NULL,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,

    day_open DOUBLE NULL,
    day_low DOUBLE NULL,
    day_high DOUBLE NULL,
    day_close DOUBLE NULL,

    radar_time DATETIME NOT NULL,
    radar_open DOUBLE NULL,
    radar_high DOUBLE NULL,
    radar_low DOUBLE NULL,
    radar_close DOUBLE NULL,
    radar_volume BIGINT NULL,
    radar_amount DOUBLE NULL,
    radar_close_return_pct DOUBLE NULL,
    radar_from_day_open_pct DOUBLE NULL,
    radar_from_day_low_pct DOUBLE NULL,

    pullback_low_time DATETIME NULL,
    pullback_low_price DOUBLE NULL,
    pullback_depth_from_radar_high_pct DOUBLE NULL,
    pullback_bars INT NULL,
    pullback_avg_volume DOUBLE NULL,
    pullback_volume_ratio_to_radar DOUBLE NULL,

    reaction_high_time DATETIME NULL,
    reaction_high_price DOUBLE NULL,

    entry_time DATETIME NULL,
    entry_price DOUBLE NULL,
    entry_from_day_open_pct DOUBLE NULL,
    entry_from_day_low_pct DOUBLE NULL,
    entry_volume BIGINT NULL,
    entry_amount DOUBLE NULL,
    entry_rsi14 DOUBLE NULL,

    entry_after_max_time DATETIME NULL,
    entry_after_max_price DOUBLE NULL,
    max_return_after_entry_pct DOUBLE NULL,
    close_return_from_entry_pct DOUBLE NULL,
    max_drawdown_after_entry_pct DOUBLE NULL,

    valid_flag TINYINT NOT NULL DEFAULT 1,
    invalid_reason VARCHAR(255) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_radar_pullback_result (radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio, search_date, search_time, code),
    KEY ix_radar_pullback_date (search_date),
    KEY ix_radar_pullback_code (code),
    KEY ix_radar_pullback_rank (actual_rank),
    KEY ix_radar_pullback_entry_open (entry_from_day_open_pct),
    KEY ix_radar_pullback_return (max_return_after_entry_pct, close_return_from_entry_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS radar_pullback_entry_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    radar_threshold_pct DOUBLE NOT NULL,
    pullback_depth_pct DOUBLE NOT NULL,
    max_pullback_bars INT NOT NULL,
    volume_shrink_ratio DOUBLE NOT NULL,

    sample_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_trade_per_day DOUBLE NULL,

    actual_top1_count INT NOT NULL DEFAULT 0,
    actual_top3_count INT NOT NULL DEFAULT 0,
    actual_top5_count INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,
    actual_top10_rate DOUBLE NULL,

    avg_entry_from_day_open_pct DOUBLE NULL,
    avg_entry_from_day_low_pct DOUBLE NULL,

    avg_max_return_after_entry_pct DOUBLE NULL,
    median_max_return_after_entry_pct DOUBLE NULL,
    avg_close_return_from_entry_pct DOUBLE NULL,
    avg_max_drawdown_after_entry_pct DOUBLE NULL,

    win_rate_after_3pct DOUBLE NULL,
    win_rate_after_5pct DOUBLE NULL,
    win_rate_after_10pct DOUBLE NULL,
    loss_rate_close_minus3pct DOUBLE NULL,
    loss_rate_close_minus5pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_radar_pullback_summary (radar_threshold_pct, pullback_depth_pct, max_pullback_bars, volume_shrink_ratio),
    KEY ix_radar_pullback_summary_sample (sample_count),
    KEY ix_radar_pullback_summary_return (avg_max_return_after_entry_pct),
    KEY ix_radar_pullback_summary_loss (loss_rate_close_minus5pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
