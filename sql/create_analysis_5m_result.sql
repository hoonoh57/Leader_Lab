CREATE TABLE IF NOT EXISTS analysis_5m_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    capture_time DATETIME NULL,
    capture_price DOUBLE NULL,

    max_after_time DATETIME NULL,
    max_after_price DOUBLE NULL,
    max_after_return_pct DOUBLE NULL,

    close_1530 DOUBLE NULL,
    close_return_pct DOUBLE NULL,

    min_after_time DATETIME NULL,
    min_after_price DOUBLE NULL,
    max_drawdown_pct DOUBLE NULL,

    base_candle_time DATETIME NULL,
    base_open DOUBLE NULL,
    base_high DOUBLE NULL,
    base_low DOUBLE NULL,
    base_close DOUBLE NULL,
    base_volume BIGINT NULL,
    base_amount DOUBLE NULL,

    cum_volume_until_capture BIGINT NULL,
    cum_amount_until_capture DOUBLE NULL,

    after_candle_count INT NOT NULL DEFAULT 0,
    cached_count INT NOT NULL DEFAULT 0,
    history_grade VARCHAR(30) NOT NULL DEFAULT 'unknown',
    valid_analysis_flag TINYINT NOT NULL DEFAULT 1,
    invalid_reason VARCHAR(255) NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_analysis_5m (search_date, search_time, code),
    KEY ix_analysis_5m_return (max_after_return_pct),
    KEY ix_analysis_5m_date_time (search_date, search_time),
    KEY ix_analysis_5m_code (code),
    KEY ix_analysis_5m_grade (history_grade)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
