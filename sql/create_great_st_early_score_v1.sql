CREATE TABLE IF NOT EXISTS great_st_early_score_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

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

    quality_label VARCHAR(20) NOT NULL,
    label_great TINYINT NOT NULL DEFAULT 0,
    label_good_or_great TINYINT NOT NULL DEFAULT 0,
    label_bad TINYINT NOT NULL DEFAULT 0,

    st_up_start_time DATETIME NOT NULL,
    st_up_end_time DATETIME NULL,
    st_up_bars INT NOT NULL DEFAULT 0,
    st_up_max_return_pct DOUBLE NULL,
    st_up_end_return_pct DOUBLE NULL,

    start_penalty_score DOUBLE NOT NULL DEFAULT 0,
    early_power_score DOUBLE NOT NULL DEFAULT 0,
    early_expansion_score DOUBLE NOT NULL DEFAULT 0,
    break_confirm_score DOUBLE NOT NULL DEFAULT 0,
    singlebar_power_score DOUBLE NOT NULL DEFAULT 0,
    score_total DOUBLE NOT NULL DEFAULT 0,

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

    score_bucket VARCHAR(30) NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_early_score_v1 (signature_id),
    KEY ix_great_st_score_date_param (trade_date, st_period, st_multiplier),
    KEY ix_great_st_score_total (score_total),
    KEY ix_great_st_score_bucket (score_bucket),
    KEY ix_great_st_score_label (quality_label, label_great, label_good_or_great, label_bad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_score_v1_daily_rank (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    score_id BIGINT NOT NULL,
    signature_id BIGINT NOT NULL,
    segment_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    quality_label VARCHAR(20) NOT NULL,
    label_great TINYINT NOT NULL DEFAULT 0,
    label_good_or_great TINYINT NOT NULL DEFAULT 0,
    label_bad TINYINT NOT NULL DEFAULT 0,
    score_total DOUBLE NOT NULL DEFAULT 0,
    rank_in_day INT NOT NULL,
    st_up_max_return_pct DOUBLE NULL,
    st_up_start_time DATETIME NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_score_daily_rank (score_id),
    KEY ix_great_st_score_rank_group (trade_date, st_period, st_multiplier, rank_in_day),
    KEY ix_great_st_score_rank_quality (rank_in_day, quality_label)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_score_v1_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    summary_group VARCHAR(80) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_score_total DOUBLE NULL,
    avg_st_up_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,
    avg_start_penalty_score DOUBLE NULL,
    avg_early_power_score DOUBLE NULL,
    avg_early_expansion_score DOUBLE NULL,
    avg_break_confirm_score DOUBLE NULL,
    avg_singlebar_power_score DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_score_summary (st_period, st_multiplier, summary_group),
    KEY ix_great_st_score_summary_quality (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_score_v1_topn_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    st_period INT NOT NULL,
    st_multiplier DOUBLE NOT NULL,
    top_n INT NOT NULL,
    group_count INT NOT NULL DEFAULT 0,
    candidate_count INT NOT NULL DEFAULT 0,
    great_hit_group_rate DOUBLE NULL,
    good_or_great_hit_group_rate DOUBLE NULL,
    bad_in_top_rate DOUBLE NULL,
    avg_top_score DOUBLE NULL,
    avg_top_st_up_max_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_score_topn (st_period, st_multiplier, top_n),
    KEY ix_great_st_score_topn_rates (great_hit_group_rate, good_or_great_hit_group_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
