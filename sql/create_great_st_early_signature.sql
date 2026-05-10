CREATE TABLE IF NOT EXISTS great_st_early_signature (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    segment_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    search_time TIME NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT 'm5',
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,

    quality_label VARCHAR(20) NOT NULL,
    st_up_start_time DATETIME NOT NULL,
    st_up_end_time DATETIME NULL,
    st_up_bars INT NOT NULL DEFAULT 0,
    st_up_start_price DOUBLE NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_up_end_return_pct DOUBLE NULL,

    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    start_cum_volume BIGINT NULL,
    start_range_so_far_pct DOUBLE NULL,
    max_singlebar_return_before_start DOUBLE NULL,
    singlebar_3pct_exists_before_start TINYINT NOT NULL DEFAULT 0,
    singlebar_5pct_exists_before_start TINYINT NOT NULL DEFAULT 0,

    early1_return_pct DOUBLE NULL,
    early1_high_return_pct DOUBLE NULL,
    early1_low_drawdown_pct DOUBLE NULL,
    early1_amount DOUBLE NULL,
    early1_volume BIGINT NULL,
    early1_singlebar_return_pct DOUBLE NULL,
    early1_break_start_high TINYINT NOT NULL DEFAULT 0,

    early2_return_pct DOUBLE NULL,
    early2_high_return_pct DOUBLE NULL,
    early2_low_drawdown_pct DOUBLE NULL,
    early2_cum_amount DOUBLE NULL,
    early2_cum_volume BIGINT NULL,
    early2_avg_amount DOUBLE NULL,
    early2_max_singlebar_return_pct DOUBLE NULL,
    early2_break_start_high TINYINT NOT NULL DEFAULT 0,
    early2_green_count INT NOT NULL DEFAULT 0,

    early3_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    early3_low_drawdown_pct DOUBLE NULL,
    early3_cum_amount DOUBLE NULL,
    early3_cum_volume BIGINT NULL,
    early3_avg_amount DOUBLE NULL,
    early3_max_singlebar_return_pct DOUBLE NULL,
    early3_break_start_high TINYINT NOT NULL DEFAULT 0,
    early3_green_count INT NOT NULL DEFAULT 0,
    early3_amount_accel_ratio DOUBLE NULL,

    label_great TINYINT NOT NULL DEFAULT 0,
    label_good_or_great TINYINT NOT NULL DEFAULT 0,
    label_bad TINYINT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_early_signature (segment_id),
    KEY ix_great_st_early_date (trade_date),
    KEY ix_great_st_early_code (code),
    KEY ix_great_st_early_param (st_period, st_multiplier),
    KEY ix_great_st_early_quality (quality_label),
    KEY ix_great_st_early_amount3 (early3_cum_amount),
    KEY ix_great_st_early_return3 (early3_high_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_signature_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    group_name VARCHAR(60) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,

    avg_st_up_max_return_pct DOUBLE NULL,
    avg_st_up_end_return_pct DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,

    avg_early1_return_pct DOUBLE NULL,
    avg_early1_high_return_pct DOUBLE NULL,
    avg_early1_amount DOUBLE NULL,
    avg_early1_singlebar_return_pct DOUBLE NULL,

    avg_early2_return_pct DOUBLE NULL,
    avg_early2_high_return_pct DOUBLE NULL,
    avg_early2_cum_amount DOUBLE NULL,
    avg_early2_max_singlebar_return_pct DOUBLE NULL,
    early2_break_start_high_rate DOUBLE NULL,

    avg_early3_return_pct DOUBLE NULL,
    avg_early3_high_return_pct DOUBLE NULL,
    avg_early3_cum_amount DOUBLE NULL,
    avg_early3_max_singlebar_return_pct DOUBLE NULL,
    avg_early3_amount_accel_ratio DOUBLE NULL,
    early3_break_start_high_rate DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_early_summary (st_period, st_multiplier, group_name),
    KEY ix_great_st_early_summary_return (avg_st_up_max_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_signature_feature_diff (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    compare_name VARCHAR(80) NOT NULL,
    feature_name VARCHAR(120) NOT NULL,
    positive_group VARCHAR(40) NOT NULL,
    negative_group VARCHAR(40) NOT NULL,
    positive_count INT NOT NULL DEFAULT 0,
    negative_count INT NOT NULL DEFAULT 0,
    positive_avg_value DOUBLE NULL,
    negative_avg_value DOUBLE NULL,
    diff_avg_value DOUBLE NULL,
    ratio_value DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_early_feature_diff (st_period, st_multiplier, compare_name, feature_name),
    KEY ix_great_st_early_feature_diff_abs (diff_avg_value),
    KEY ix_great_st_early_feature_name (feature_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
