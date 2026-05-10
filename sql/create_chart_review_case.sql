CREATE TABLE IF NOT EXISTS chart_review_case (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    threshold_pct DOUBLE NOT NULL,
    entry_filter_name VARCHAR(80) NOT NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,

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
    singlebar_close_return_pct DOUBLE NULL,
    singlebar_from_day_open_pct DOUBLE NULL,

    break_time DATETIME NULL,
    break_price DOUBLE NULL,
    break_rsi14 DOUBLE NULL,
    break_from_day_open_pct DOUBLE NULL,

    entry_time DATETIME NULL,
    entry_price DOUBLE NULL,
    entry_from_day_open_pct DOUBLE NULL,

    day_high_after_entry DOUBLE NULL,
    max_return_after_entry_pct DOUBLE NULL,
    close_return_from_entry_pct DOUBLE NULL,
    max_drawdown_after_entry_pct DOUBLE NULL,

    review_tag VARCHAR(80) NULL,
    review_memo TEXT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_chart_review_case (search_date, search_time, code, threshold_pct, entry_filter_name),
    KEY ix_chart_review_date (search_date),
    KEY ix_chart_review_code (code),
    KEY ix_chart_review_filter (threshold_pct, entry_filter_name),
    KEY ix_chart_review_actual_rank (actual_rank),
    KEY ix_chart_review_entry_open_pct (entry_from_day_open_pct),
    KEY ix_chart_review_return (max_return_after_entry_pct, close_return_from_entry_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
