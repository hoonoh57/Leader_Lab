CREATE TABLE IF NOT EXISTS stock_info.leader_daily_features (
    performance_id BIGINT UNSIGNED NOT NULL,
    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code CHAR(6) NOT NULL,

    recent_high20_break_within_10d TINYINT(1) NOT NULL DEFAULT 0,
    recent_high60_break_within_20d TINYINT(1) NOT NULL DEFAULT 0,

    has_daily_base_bar TINYINT(1) NOT NULL DEFAULT 0,
    daily_base_date DATE NULL,
    daily_base_return DECIMAL(8,3) NULL,
    daily_base_amount BIGINT UNSIGNED NULL,
    daily_base_close_position DECIMAL(8,4) NULL,
    days_since_daily_base INT NULL,

    pullback_depth_pct DECIMAL(8,3) NULL,
    price_above_base_mid TINYINT(1) NOT NULL DEFAULT 0,
    price_near_base_high TINYINT(1) NOT NULL DEFAULT 0,
    rebreak_daily_base_high TINYINT(1) NOT NULL DEFAULT 0,

    ma5 DECIMAL(14,4) NULL,
    ma20 DECIMAL(14,4) NULL,
    ma60 DECIMAL(14,4) NULL,
    ma5_above_ma20 TINYINT(1) NOT NULL DEFAULT 0,
    ma20_slope DECIMAL(10,4) NULL,
    overextended_20d TINYINT(1) NOT NULL DEFAULT 0,

    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (performance_id),
    KEY idx_ldf_date (search_date, search_time),
    KEY idx_ldf_code_date (code, search_date),
    KEY idx_ldf_base (has_daily_base_bar, rebreak_daily_base_high),

    CONSTRAINT fk_ldf_perf
        FOREIGN KEY (performance_id)
        REFERENCES stock_info.performance_result(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS stock_info.leader_5m_features (
    performance_id BIGINT UNSIGNED NOT NULL,
    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code CHAR(6) NOT NULL,

    has_intraday_base_bar TINYINT(1) NOT NULL DEFAULT 0,
    intraday_base_time DATETIME NULL,
    intraday_base_return DECIMAL(8,3) NULL,
    intraday_base_amount BIGINT UNSIGNED NULL,
    intraday_base_close_position DECIMAL(8,4) NULL,
    intraday_base_high INT NULL,
    intraday_base_low INT NULL,
    intraday_base_mid DECIMAL(14,4) NULL,

    break_intraday_base_high TINYINT(1) NOT NULL DEFAULT 0,
    break_time DATETIME NULL,
    minutes_to_break INT NULL,

    max_5m_return DECIMAL(8,3) NULL,
    max_5m_amount BIGINT UNSIGNED NULL,

    rsi14_at_search DECIMAL(8,3) NULL,
    rsi_cross60_before TINYINT(1) NOT NULL DEFAULT 0,
    rsi_pullback_after_cross TINYINT(1) NOT NULL DEFAULT 0,
    rsi_recross60 TINYINT(1) NOT NULL DEFAULT 0,

    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (performance_id),
    KEY idx_l5m_date (search_date, search_time),
    KEY idx_l5m_code_date (code, search_date),
    KEY idx_l5m_base (has_intraday_base_bar, break_intraday_base_high),

    CONSTRAINT fk_l5m_perf
        FOREIGN KEY (performance_id)
        REFERENCES stock_info.performance_result(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci;
