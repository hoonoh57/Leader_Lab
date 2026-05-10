CREATE TABLE IF NOT EXISTS winner_pattern_case (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,
    close_return_pct DOUBLE NULL,

    group_top3 TINYINT NOT NULL DEFAULT 0,
    group_top5 TINYINT NOT NULL DEFAULT 0,
    group_top10 TINYINT NOT NULL DEFAULT 0,
    group_ret10 TINYINT NOT NULL DEFAULT 0,
    group_ret15 TINYINT NOT NULL DEFAULT 0,
    group_low3 TINYINT NOT NULL DEFAULT 0,
    group_close_m3 TINYINT NOT NULL DEFAULT 0,
    group_close_m5 TINYINT NOT NULL DEFAULT 0,

    day_open DOUBLE NULL,
    day_high DOUBLE NULL,
    day_low DOUBLE NULL,
    day_close DOUBLE NULL,
    day_range_pct DOUBLE NULL,
    close_from_open_pct DOUBLE NULL,

    first_hour_high_from_open_pct DOUBLE NULL,
    max_5m_singlebar_return_pct DOUBLE NULL,
    max_5m_singlebar_from_open_pct DOUBLE NULL,
    max_5m_singlebar_from_low_pct DOUBLE NULL,

    singlebar_2pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_3pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_4pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_5pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_6pct_exists TINYINT NOT NULL DEFAULT 0,

    max_5m_volume BIGINT NULL,
    total_5m_volume BIGINT NULL,
    intraday_amount_proxy DOUBLE NULL,

    radar_pullback_exists TINYINT NOT NULL DEFAULT 0,
    best_radar_pullback_max_return_pct DOUBLE NULL,
    best_radar_pullback_close_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_pattern_case (search_date, search_time, code),
    KEY ix_winner_pattern_date (search_date),
    KEY ix_winner_pattern_code (code),
    KEY ix_winner_pattern_rank (actual_rank),
    KEY ix_winner_pattern_ret (actual_max_after_return_pct),
    KEY ix_winner_pattern_groups (group_top5, group_ret10, group_low3)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS winner_pattern_feature_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    feature_name VARCHAR(120) NOT NULL,
    feature_type VARCHAR(40) NOT NULL,
    winner_group VARCHAR(40) NOT NULL,
    loser_group VARCHAR(40) NOT NULL,

    winner_count INT NOT NULL DEFAULT 0,
    loser_count INT NOT NULL DEFAULT 0,
    winner_rate DOUBLE NULL,
    loser_rate DOUBLE NULL,
    diff_rate DOUBLE NULL,
    lift_ratio DOUBLE NULL,

    winner_avg_value DOUBLE NULL,
    loser_avg_value DOUBLE NULL,
    diff_avg_value DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_feature_summary (feature_name, feature_type, winner_group, loser_group),
    KEY ix_winner_feature_diff (diff_rate),
    KEY ix_winner_feature_lift (lift_ratio),
    KEY ix_winner_feature_name (feature_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
