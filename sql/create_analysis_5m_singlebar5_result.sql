CREATE TABLE IF NOT EXISTS analysis_5m_singlebar5_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    capture_time DATETIME NULL,
    capture_price DOUBLE NULL,
    actual_max_after_return_pct DOUBLE NULL,
    actual_rank INT NULL,
    in_actual_top10 TINYINT NOT NULL DEFAULT 0,

    day_open DOUBLE NULL,
    day_high DOUBLE NULL,
    day_low DOUBLE NULL,
    day_close DOUBLE NULL,

    singlebar_time DATETIME NULL,
    singlebar_open DOUBLE NULL,
    singlebar_high DOUBLE NULL,
    singlebar_low DOUBLE NULL,
    singlebar_close DOUBLE NULL,
    singlebar_volume BIGINT NULL,
    singlebar_amount DOUBLE NULL,

    singlebar_close_return_pct DOUBLE NULL,
    singlebar_high_return_pct DOUBLE NULL,
    singlebar_close_position_pct DOUBLE NULL,
    singlebar_from_day_open_close_pct DOUBLE NULL,
    singlebar_from_day_open_high_pct DOUBLE NULL,

    has_singlebar_close5 TINYINT NOT NULL DEFAULT 0,
    singlebar_rank_by_time INT NULL,
    singlebar_rank_by_return INT NULL,

    next_break_time DATETIME NULL,
    next_break_type VARCHAR(30) NULL,
    next_break_price DOUBLE NULL,
    bars_to_next_break INT NULL,
    low_broken_before_next_break TINYINT NOT NULL DEFAULT 0,

    after_singlebar_max_time DATETIME NULL,
    after_singlebar_max_price DOUBLE NULL,
    after_singlebar_max_return_pct DOUBLE NULL,
    after_singlebar_close_return_pct DOUBLE NULL,
    after_singlebar_max_drawdown_pct DOUBLE NULL,

    valid_flag TINYINT NOT NULL DEFAULT 1,
    invalid_reason VARCHAR(255) NULL,
    history_grade VARCHAR(30) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_singlebar5_result (search_date, search_time, code),
    KEY ix_singlebar5_date (search_date),
    KEY ix_singlebar5_code (code),
    KEY ix_singlebar5_has (has_singlebar_close5),
    KEY ix_singlebar5_actual_rank (actual_rank),
    KEY ix_singlebar5_return (after_singlebar_max_return_pct),
    KEY ix_singlebar5_bar_time (singlebar_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS analysis_5m_singlebar5_daily_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    eval_date DATE NOT NULL,
    eligible_rows INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,
    singlebar5_count INT NOT NULL DEFAULT 0,
    singlebar5_actual_top10_count INT NOT NULL DEFAULT 0,
    singlebar5_hit_at_10 INT NOT NULL DEFAULT 0,
    singlebar5_hit_rate DOUBLE NULL,

    avg_actual_top10_return_pct DOUBLE NULL,
    avg_singlebar5_actual_return_pct DOUBLE NULL,
    avg_singlebar5_after_max_return_pct DOUBLE NULL,
    avg_singlebar5_after_close_return_pct DOUBLE NULL,
    avg_singlebar5_drawdown_pct DOUBLE NULL,

    win_rate_after_3pct DOUBLE NULL,
    win_rate_after_5pct DOUBLE NULL,
    win_rate_after_10pct DOUBLE NULL,
    win_rate_after_20pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_singlebar5_daily (eval_date),
    KEY ix_singlebar5_daily_hit (singlebar5_hit_at_10),
    KEY ix_singlebar5_daily_count (singlebar5_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
