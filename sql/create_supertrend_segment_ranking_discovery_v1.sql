CREATE TABLE IF NOT EXISTS st_segment_ranking_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

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
    st_up_bars INT NOT NULL DEFAULT 0,
    quality_label VARCHAR(20) NOT NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_up_end_return_pct DOUBLE NULL,

    score_total DOUBLE NOT NULL DEFAULT 0,
    start_penalty_score DOUBLE NOT NULL DEFAULT 0,
    early_power_score DOUBLE NOT NULL DEFAULT 0,
    early_expansion_score DOUBLE NOT NULL DEFAULT 0,
    break_confirm_score DOUBLE NOT NULL DEFAULT 0,
    singlebar_power_score DOUBLE NOT NULL DEFAULT 0,

    rank_return_in_stock_param INT NOT NULL,
    rank_score_in_stock_param INT NOT NULL,
    is_return_rank1 TINYINT NOT NULL DEFAULT 0,
    is_score_rank1 TINYINT NOT NULL DEFAULT 0,
    score_rank_matches_return_rank1 TINYINT NOT NULL DEFAULT 0,

    segment_count_in_stock_param INT NOT NULL DEFAULT 0,
    return_rank_of_score_rank1 INT NULL,

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
    early2_break_start_high TINYINT NOT NULL DEFAULT 0,
    early3_break_start_high TINYINT NOT NULL DEFAULT 0,
    early2_max_singlebar_return_pct DOUBLE NULL,
    early3_max_singlebar_return_pct DOUBLE NULL,

    segment_state_label VARCHAR(60) NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_segment_ranking_v1 (score_id),
    KEY ix_st_seg_rank_group (trade_date, code, st_period, st_multiplier, rank_score_in_stock_param),
    KEY ix_st_seg_rank_return (trade_date, code, st_period, st_multiplier, rank_return_in_stock_param),
    KEY ix_st_seg_rank_state (segment_state_label),
    KEY ix_st_seg_rank_quality (quality_label, label_great, label_good_or_great, label_bad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_rank_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    rank_type VARCHAR(40) NOT NULL,
    rank_value INT NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_st_up_max_return_pct DOUBLE NULL,
    median_st_up_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    return_rank1_rate DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_rank_summary (st_period, st_multiplier, rank_type, rank_value),
    KEY ix_st_seg_rank_summary_rates (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_state_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    segment_state_label VARCHAR(60) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_st_up_max_return_pct DOUBLE NULL,
    median_st_up_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,
    avg_score_total DOUBLE NULL,
    avg_st_up_bars DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_state_summary (st_period, st_multiplier, segment_state_label),
    KEY ix_st_seg_state_summary_rates (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS st_segment_ranking_alignment_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    stock_param_group_count INT NOT NULL DEFAULT 0,
    avg_segment_count DOUBLE NULL,
    score_rank1_is_return_rank1_rate DOUBLE NULL,
    score_rank1_is_great_rate DOUBLE NULL,
    score_rank1_is_good_or_great_rate DOUBLE NULL,
    score_rank1_is_bad_rate DOUBLE NULL,
    avg_return_rank_of_score_rank1 DOUBLE NULL,
    avg_score_rank1_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_st_seg_alignment_summary (st_period, st_multiplier),
    KEY ix_st_seg_alignment_rates (score_rank1_is_return_rank1_rate, score_rank1_is_good_or_great_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
