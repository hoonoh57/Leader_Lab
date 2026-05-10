CREATE TABLE IF NOT EXISTS winner_feature_score_time_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    decision_time TIME NOT NULL,
    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,
    full_day_close_return_pct DOUBLE NULL,

    decision_candle_time DATETIME NULL,
    decision_price DOUBLE NULL,

    future_max_price DOUBLE NULL,
    future_min_price DOUBLE NULL,
    future_close_price DOUBLE NULL,
    future_max_return_pct DOUBLE NULL,
    future_close_return_pct DOUBLE NULL,
    future_max_drawdown_pct DOUBLE NULL,

    leader_strength_score_time DOUBLE NOT NULL DEFAULT 0,
    pullback_structure_score_time DOUBLE NOT NULL DEFAULT 0,
    current_strength_score_time DOUBLE NOT NULL DEFAULT 0,
    overheat_penalty_time DOUBLE NOT NULL DEFAULT 0,
    winner_feature_score_time DOUBLE NOT NULL DEFAULT 0,

    cum_amount_until_time DOUBLE NULL,
    cum_volume_until_time BIGINT NULL,
    current_close_from_open_pct DOUBLE NULL,
    high_so_far_from_open_pct DOUBLE NULL,
    high_so_far_from_low_pct DOUBLE NULL,
    range_so_far_pct DOUBLE NULL,

    singlebar_2pct_exists_until_time TINYINT NOT NULL DEFAULT 0,
    singlebar_3pct_exists_until_time TINYINT NOT NULL DEFAULT 0,
    singlebar_4pct_exists_until_time TINYINT NOT NULL DEFAULT 0,
    singlebar_5pct_exists_until_time TINYINT NOT NULL DEFAULT 0,
    singlebar_6pct_exists_until_time TINYINT NOT NULL DEFAULT 0,
    max_singlebar_return_until_time DOUBLE NULL,
    max_singlebar_from_open_until_time DOUBLE NULL,
    max_singlebar_from_low_until_time DOUBLE NULL,

    radar_pullback_exists_until_time TINYINT NOT NULL DEFAULT 0,
    radar_pullback_best_max_return_until_time DOUBLE NULL,

    amount_score_time DOUBLE NOT NULL DEFAULT 0,
    high_score_time DOUBLE NOT NULL DEFAULT 0,
    range_score_time DOUBLE NOT NULL DEFAULT 0,
    singlebar_score_time DOUBLE NOT NULL DEFAULT 0,
    radar_pullback_score_time DOUBLE NOT NULL DEFAULT 0,
    current_close_score_time DOUBLE NOT NULL DEFAULT 0,
    singlebar6_penalty_time DOUBLE NOT NULL DEFAULT 0,
    overheat_open_penalty_time DOUBLE NOT NULL DEFAULT 0,
    overheat_low_penalty_time DOUBLE NOT NULL DEFAULT 0,

    score_rank_time INT NULL,
    score_bucket_time VARCHAR(40) NULL,
    actual_rank_bucket VARCHAR(40) NULL,

    valid_flag TINYINT NOT NULL DEFAULT 1,
    invalid_reason VARCHAR(255) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_feature_score_time (decision_time, search_date, search_time, code),
    KEY ix_winner_feature_score_time_rank (decision_time, search_date, score_rank_time),
    KEY ix_winner_feature_score_time_score (decision_time, winner_feature_score_time),
    KEY ix_winner_feature_score_time_actual (actual_rank),
    KEY ix_winner_feature_score_time_return (future_max_return_pct, future_close_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS winner_feature_score_time_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    decision_time TIME NOT NULL,
    score_group VARCHAR(60) NOT NULL,
    sample_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_candidates_per_day DOUBLE NULL,

    actual_top1_count INT NOT NULL DEFAULT 0,
    actual_top3_count INT NOT NULL DEFAULT 0,
    actual_top5_count INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,
    actual_top10_rate DOUBLE NULL,

    avg_future_max_return_pct DOUBLE NULL,
    median_future_max_return_pct DOUBLE NULL,
    avg_future_close_return_pct DOUBLE NULL,
    avg_future_max_drawdown_pct DOUBLE NULL,

    win_rate_future_3pct DOUBLE NULL,
    win_rate_future_5pct DOUBLE NULL,
    win_rate_future_10pct DOUBLE NULL,
    loss_rate_future_close_m3pct DOUBLE NULL,
    loss_rate_future_close_m5pct DOUBLE NULL,

    avg_winner_feature_score_time DOUBLE NULL,
    avg_leader_strength_score_time DOUBLE NULL,
    avg_pullback_structure_score_time DOUBLE NULL,
    avg_current_strength_score_time DOUBLE NULL,
    avg_overheat_penalty_time DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_winner_feature_score_time_summary (decision_time, score_group),
    KEY ix_winner_feature_score_time_summary_top10 (actual_top10_rate),
    KEY ix_winner_feature_score_time_summary_return (avg_future_max_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
