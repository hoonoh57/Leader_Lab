CREATE TABLE IF NOT EXISTS winner_feature_score_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,
    close_return_pct DOUBLE NULL,

    leader_strength_score DOUBLE NOT NULL DEFAULT 0,
    pullback_structure_score DOUBLE NOT NULL DEFAULT 0,
    close_strength_score DOUBLE NOT NULL DEFAULT 0,
    overheat_penalty DOUBLE NOT NULL DEFAULT 0,
    winner_feature_score DOUBLE NOT NULL DEFAULT 0,

    amount_score DOUBLE NOT NULL DEFAULT 0,
    first_hour_score DOUBLE NOT NULL DEFAULT 0,
    day_range_score DOUBLE NOT NULL DEFAULT 0,
    singlebar_score DOUBLE NOT NULL DEFAULT 0,
    radar_pullback_score DOUBLE NOT NULL DEFAULT 0,
    radar_pullback_return_score DOUBLE NOT NULL DEFAULT 0,
    close_from_open_score DOUBLE NOT NULL DEFAULT 0,
    radar_close_return_score DOUBLE NOT NULL DEFAULT 0,
    singlebar6_penalty DOUBLE NOT NULL DEFAULT 0,
    singlebar_open_overheat_penalty DOUBLE NOT NULL DEFAULT 0,
    singlebar_low_overheat_penalty DOUBLE NOT NULL DEFAULT 0,

    intraday_amount_proxy DOUBLE NULL,
    first_hour_high_from_open_pct DOUBLE NULL,
    day_range_pct DOUBLE NULL,
    close_from_open_pct DOUBLE NULL,
    max_5m_singlebar_return_pct DOUBLE NULL,
    max_5m_singlebar_from_open_pct DOUBLE NULL,
    max_5m_singlebar_from_low_pct DOUBLE NULL,
    best_radar_pullback_max_return_pct DOUBLE NULL,
    best_radar_pullback_close_return_pct DOUBLE NULL,

    singlebar_2pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_3pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_4pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_5pct_exists TINYINT NOT NULL DEFAULT 0,
    singlebar_6pct_exists TINYINT NOT NULL DEFAULT 0,
    radar_pullback_exists TINYINT NOT NULL DEFAULT 0,

    score_rank INT NULL,
    actual_rank_bucket VARCHAR(40) NULL,
    score_bucket VARCHAR(40) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_feature_score_result (search_date, search_time, code),
    KEY ix_winner_feature_date_score (search_date, winner_feature_score),
    KEY ix_winner_feature_rank (score_rank),
    KEY ix_winner_feature_actual_rank (actual_rank),
    KEY ix_winner_feature_score (winner_feature_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS winner_feature_score_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    score_group VARCHAR(60) NOT NULL,
    sample_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_candidates_per_day DOUBLE NULL,

    actual_top1_count INT NOT NULL DEFAULT 0,
    actual_top3_count INT NOT NULL DEFAULT 0,
    actual_top5_count INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,
    actual_top10_rate DOUBLE NULL,

    avg_actual_max_after_return_pct DOUBLE NULL,
    median_actual_max_after_return_pct DOUBLE NULL,
    avg_close_return_pct DOUBLE NULL,

    avg_winner_feature_score DOUBLE NULL,
    avg_leader_strength_score DOUBLE NULL,
    avg_pullback_structure_score DOUBLE NULL,
    avg_close_strength_score DOUBLE NULL,
    avg_overheat_penalty DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_feature_score_summary (score_group),
    KEY ix_winner_feature_summary_top10 (actual_top10_rate),
    KEY ix_winner_feature_summary_return (avg_actual_max_after_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
