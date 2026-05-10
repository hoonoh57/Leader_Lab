CREATE TABLE IF NOT EXISTS analysis_5m_basebar_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    day_open DOUBLE NULL,
    day_high DOUBLE NULL,
    day_low DOUBLE NULL,
    day_close DOUBLE NULL,

    capture_time DATETIME NULL,
    capture_price DOUBLE NULL,
    capture_to_day_high_return_pct DOUBLE NULL,
    capture_to_close_return_pct DOUBLE NULL,

    base_candle_time DATETIME NULL,
    base_open DOUBLE NULL,
    base_high DOUBLE NULL,
    base_low DOUBLE NULL,
    base_close DOUBLE NULL,
    base_volume BIGINT NULL,
    base_amount DOUBLE NULL,

    bar_return_pct DOUBLE NULL,
    from_day_open_close_pct DOUBLE NULL,
    from_day_open_high_pct DOUBLE NULL,
    close_position_pct DOUBLE NULL,

    is_bar_return_5 TINYINT NOT NULL DEFAULT 0,
    is_from_day_open_close_5 TINYINT NOT NULL DEFAULT 0,
    is_from_day_open_high_5 TINYINT NOT NULL DEFAULT 0,

    base_low_broken_before_break TINYINT NOT NULL DEFAULT 0,
    max_pullback_before_break_pct DOUBLE NULL,

    break_time DATETIME NULL,
    break_price DOUBLE NULL,
    break_type VARCHAR(30) NULL,
    bars_to_break INT NULL,
    bars_after_break INT NULL,

    break_after_max_time DATETIME NULL,
    break_after_max_price DOUBLE NULL,
    break_after_max_return_pct DOUBLE NULL,
    break_after_close_return_pct DOUBLE NULL,
    break_after_max_drawdown_pct DOUBLE NULL,

    pattern_type VARCHAR(80) NOT NULL DEFAULT 'none',
    valid_flag TINYINT NOT NULL DEFAULT 1,
    invalid_reason VARCHAR(255) NULL,
    history_grade VARCHAR(30) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_basebar_result (search_date, search_time, code),
    KEY ix_basebar_date (search_date),
    KEY ix_basebar_code (code),
    KEY ix_basebar_pattern (pattern_type),
    KEY ix_basebar_valid (valid_flag),
    KEY ix_basebar_break_return (break_after_max_return_pct),
    KEY ix_basebar_base_time (base_candle_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS analysis_5m_basebar_pattern_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    pattern_name VARCHAR(80) NOT NULL,
    sample_count INT NOT NULL DEFAULT 0,
    break_count INT NOT NULL DEFAULT 0,
    break_rate DOUBLE NULL,

    avg_capture_to_day_high_return_pct DOUBLE NULL,
    avg_capture_to_close_return_pct DOUBLE NULL,

    avg_break_after_max_return_pct DOUBLE NULL,
    median_break_after_max_return_pct DOUBLE NULL,
    avg_break_after_close_return_pct DOUBLE NULL,
    avg_break_after_max_drawdown_pct DOUBLE NULL,

    win_rate_3pct DOUBLE NULL,
    win_rate_5pct DOUBLE NULL,
    win_rate_10pct DOUBLE NULL,
    win_rate_20pct DOUBLE NULL,

    avg_bars_to_break DOUBLE NULL,
    avg_bars_after_break DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_basebar_pattern_summary (pattern_name),
    KEY ix_basebar_pattern_sample (sample_count),
    KEY ix_basebar_pattern_return (avg_break_after_max_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
