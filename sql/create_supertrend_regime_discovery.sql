CREATE TABLE IF NOT EXISTS supertrend_regime_segment (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    trade_date DATE NOT NULL,
    search_time TIME NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT 'm5',

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,

    capture_time DATETIME NULL,
    already_up_at_capture TINYINT NOT NULL DEFAULT 0,

    st_up_start_time DATETIME NOT NULL,
    st_up_end_time DATETIME NULL,
    st_up_bars INT NOT NULL DEFAULT 0,

    st_up_start_price DOUBLE NULL,
    st_up_max_price DOUBLE NULL,
    st_up_end_price DOUBLE NULL,
    st_up_min_price DOUBLE NULL,

    st_up_max_return_pct DOUBLE NULL,
    st_up_end_return_pct DOUBLE NULL,
    st_up_max_drawdown_pct DOUBLE NULL,

    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    start_cum_volume BIGINT NULL,
    start_range_so_far_pct DOUBLE NULL,
    start_high_so_far_from_open_pct DOUBLE NULL,
    max_singlebar_return_before_start DOUBLE NULL,
    singlebar_3pct_exists_before_start TINYINT NOT NULL DEFAULT 0,
    singlebar_5pct_exists_before_start TINYINT NOT NULL DEFAULT 0,

    segment_amount DOUBLE NULL,
    segment_volume BIGINT NULL,
    segment_avg_amount_per_bar DOUBLE NULL,
    segment_max_singlebar_return_pct DOUBLE NULL,
    segment_green_bar_count INT NOT NULL DEFAULT 0,
    segment_red_bar_count INT NOT NULL DEFAULT 0,

    label_st_gain_3pct TINYINT NOT NULL DEFAULT 0,
    label_st_gain_5pct TINYINT NOT NULL DEFAULT 0,
    label_st_gain_10pct TINYINT NOT NULL DEFAULT 0,
    label_st_fail_1pct TINYINT NOT NULL DEFAULT 0,
    label_st_end_negative TINYINT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_regime_segment (trade_date, code, timeframe, st_period, st_multiplier, segment_no),
    KEY ix_st_regime_date (trade_date),
    KEY ix_st_regime_code (code),
    KEY ix_st_regime_param (st_period, st_multiplier),
    KEY ix_st_regime_return (st_up_max_return_pct, st_up_end_return_pct),
    KEY ix_st_regime_labels (label_st_gain_5pct, label_st_fail_1pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS supertrend_regime_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_group VARCHAR(60) NOT NULL,

    segment_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_segments_per_day DOUBLE NULL,

    avg_st_up_bars DOUBLE NULL,
    avg_st_up_max_return_pct DOUBLE NULL,
    median_st_up_max_return_pct DOUBLE NULL,
    avg_st_up_end_return_pct DOUBLE NULL,
    avg_st_up_max_drawdown_pct DOUBLE NULL,

    gain3_rate DOUBLE NULL,
    gain5_rate DOUBLE NULL,
    gain10_rate DOUBLE NULL,
    fail1_rate DOUBLE NULL,
    end_negative_rate DOUBLE NULL,

    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    avg_start_range_so_far_pct DOUBLE NULL,
    avg_segment_amount DOUBLE NULL,
    avg_segment_max_singlebar_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_regime_summary (st_period, st_multiplier, segment_group),
    KEY ix_st_regime_summary_return (avg_st_up_max_return_pct),
    KEY ix_st_regime_summary_gain5 (gain5_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS supertrend_regime_feature_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    feature_name VARCHAR(120) NOT NULL,
    good_group VARCHAR(60) NOT NULL,
    bad_group VARCHAR(60) NOT NULL,

    good_count INT NOT NULL DEFAULT 0,
    bad_count INT NOT NULL DEFAULT 0,
    good_avg_value DOUBLE NULL,
    bad_avg_value DOUBLE NULL,
    diff_avg_value DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_regime_feature_summary (st_period, st_multiplier, feature_name, good_group, bad_group),
    KEY ix_st_regime_feature_diff (diff_avg_value),
    KEY ix_st_regime_feature_name (feature_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
