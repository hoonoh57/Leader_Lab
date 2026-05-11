CREATE TABLE IF NOT EXISTS st_segment_ranking_v1_1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    base_ranking_id BIGINT NOT NULL,
    score_id BIGINT NOT NULL,
    signature_id BIGINT NOT NULL,
    segment_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    search_time TIME NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT 'm5',
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,

    st_up_start_time DATETIME NOT NULL,
    st_up_end_time DATETIME NULL,
    st_start_minutes_from_open INT NULL,
    st_up_bars INT NOT NULL DEFAULT 0,
    quality_label VARCHAR(20) NOT NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_up_end_return_pct DOUBLE NULL,

    score_total DOUBLE NOT NULL DEFAULT 0,
    rank_return_in_stock_param INT NOT NULL,
    rank_score_in_stock_param INT NOT NULL,
    is_return_rank1 TINYINT NOT NULL DEFAULT 0,
    is_score_rank1 TINYINT NOT NULL DEFAULT 0,
    score_rank_matches_return_rank1 TINYINT NOT NULL DEFAULT 0,
    segment_count_in_stock_param INT NOT NULL DEFAULT 0,

    label_great TINYINT NOT NULL DEFAULT 0,
    label_good_or_great TINYINT NOT NULL DEFAULT 0,
    label_bad TINYINT NOT NULL DEFAULT 0,

    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,
    early1_amount DOUBLE NULL,
    early2_cum_amount DOUBLE NULL,
    early3_cum_amount DOUBLE NULL,
    early1_high_return_pct DOUBLE NULL,
    early2_high_return_pct DOUBLE NULL,
    early3_high_return_pct DOUBLE NULL,
    early2_return_pct DOUBLE NULL,
    early3_return_pct DOUBLE NULL,
    early3_close_retention_ratio DOUBLE NULL,
    early2_to_early3_amount_growth DOUBLE NULL,
    early2_break_start_high TINYINT NOT NULL DEFAULT 0,
    early3_break_start_high TINYINT NOT NULL DEFAULT 0,
    early2_max_singlebar_return_pct DOUBLE NULL,
    early3_max_singlebar_return_pct DOUBLE NULL,

    old_segment_state_label VARCHAR(60) NOT NULL,
    segment_state_label_v1_1 VARCHAR(60) NOT NULL,
    false_positive_flag TINYINT NOT NULL DEFAULT 0,
    positive_rank1_flag TINYINT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_segment_ranking_v1_1 (base_ranking_id),
    KEY ix_st_seg_rank_v11_group (trade_date, code, st_period, st_multiplier, rank_score_in_stock_param),
    KEY ix_st_seg_rank_v11_state (segment_state_label_v1_1),
    KEY ix_st_seg_rank_v11_quality (quality_label, label_great, label_good_or_great, label_bad),
    KEY ix_st_seg_rank_v11_fp (false_positive_flag, positive_rank1_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_state_summary_v1_1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_state_label_v1_1 VARCHAR(60) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_st_up_max_return_pct DOUBLE NULL,
    median_st_up_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_st_up_bars DOUBLE NULL,
    avg_st_start_minutes_from_open DOUBLE NULL,
    avg_early3_close_retention_ratio DOUBLE NULL,
    avg_early2_to_early3_amount_growth DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_state_summary_v11 (st_period, st_multiplier, segment_state_label_v1_1),
    KEY ix_st_seg_state_summary_v11_rates (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_score_rank1_quality_compare_v1_1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    compare_group VARCHAR(40) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_st_up_max_return_pct DOUBLE NULL,
    median_st_up_max_return_pct DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_st_up_bars DOUBLE NULL,
    avg_st_start_minutes_from_open DOUBLE NULL,
    avg_start_from_day_open_pct DOUBLE NULL,
    avg_start_from_day_low_pct DOUBLE NULL,
    avg_start_cum_amount DOUBLE NULL,
    avg_early1_amount DOUBLE NULL,
    avg_early2_cum_amount DOUBLE NULL,
    avg_early3_cum_amount DOUBLE NULL,
    avg_early1_high_return_pct DOUBLE NULL,
    avg_early2_high_return_pct DOUBLE NULL,
    avg_early3_high_return_pct DOUBLE NULL,
    avg_early2_return_pct DOUBLE NULL,
    avg_early3_return_pct DOUBLE NULL,
    avg_early3_close_retention_ratio DOUBLE NULL,
    avg_early2_to_early3_amount_growth DOUBLE NULL,
    early3_break_start_high_rate DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_rank1_compare_v11 (st_period, st_multiplier, compare_group),
    KEY ix_st_seg_rank1_compare_v11_group (compare_group)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_false_positive_examples_v1_1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    base_ranking_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_no INT NOT NULL,
    st_up_start_time DATETIME NOT NULL,
    score_total DOUBLE NOT NULL DEFAULT 0,
    st_up_max_return_pct DOUBLE NULL,
    quality_label VARCHAR(20) NOT NULL,
    segment_state_label_v1_1 VARCHAR(60) NOT NULL,
    rank_return_in_stock_param INT NOT NULL,
    early3_high_return_pct DOUBLE NULL,
    early3_return_pct DOUBLE NULL,
    early3_close_retention_ratio DOUBLE NULL,
    early3_cum_amount DOUBLE NULL,
    start_from_day_open_pct DOUBLE NULL,
    start_from_day_low_pct DOUBLE NULL,
    start_cum_amount DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_fp_examples_v11 (base_ranking_id),
    KEY ix_st_seg_fp_examples_v11_date_code (trade_date, code),
    KEY ix_st_seg_fp_examples_v11_score (score_total, st_up_max_return_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
