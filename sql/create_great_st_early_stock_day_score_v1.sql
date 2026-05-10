CREATE TABLE IF NOT EXISTS great_st_early_stock_day_score_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    stock_score_v1 DOUBLE NOT NULL DEFAULT 0,
    base_score DOUBLE NOT NULL DEFAULT 0,
    strong_confirm_bonus DOUBLE NOT NULL DEFAULT 0,
    mid_confirm_bonus DOUBLE NOT NULL DEFAULT 0,
    bad_penalty DOUBLE NOT NULL DEFAULT 0,

    param_count INT NOT NULL DEFAULT 0,
    score_ge_80_param_count INT NOT NULL DEFAULT 0,
    score_ge_60_param_count INT NOT NULL DEFAULT 0,
    score_ge_40_param_count INT NOT NULL DEFAULT 0,
    great_param_count INT NOT NULL DEFAULT 0,
    good_or_great_param_count INT NOT NULL DEFAULT 0,
    bad_param_count INT NOT NULL DEFAULT 0,

    param_score_max DOUBLE NULL,
    param_score_avg DOUBLE NULL,
    param_score_sum DOUBLE NULL,
    param_score_top2_avg DOUBLE NULL,
    param_score_top3_avg DOUBLE NULL,

    stock_max_return_pct DOUBLE NULL,
    stock_best_quality_label VARCHAR(20) NULL,
    stock_has_great TINYINT NOT NULL DEFAULT 0,
    stock_has_good_or_great TINYINT NOT NULL DEFAULT 0,
    stock_has_bad TINYINT NOT NULL DEFAULT 0,

    best_score_id BIGINT NULL,
    best_signature_id BIGINT NULL,
    best_segment_id BIGINT NULL,
    best_st_period INT NULL,
    best_st_multiplier DOUBLE NULL,
    best_quality_label VARCHAR(20) NULL,
    best_st_up_max_return_pct DOUBLE NULL,
    best_st_up_start_time DATETIME NULL,

    best_early3_cum_amount DOUBLE NULL,
    best_early3_high_return_pct DOUBLE NULL,
    best_start_cum_amount DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_stock_day (trade_date, code),
    KEY ix_great_st_stock_score (stock_score_v1),
    KEY ix_great_st_stock_confirm80 (score_ge_80_param_count),
    KEY ix_great_st_stock_confirm60 (score_ge_60_param_count),
    KEY ix_great_st_stock_outcome (stock_has_great, stock_has_good_or_great, stock_has_bad),
    KEY ix_great_st_stock_best_param (best_st_period, best_st_multiplier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_stock_day_rank_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    stock_day_score_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,
    rank_in_day INT NOT NULL,
    stock_score_v1 DOUBLE NOT NULL DEFAULT 0,

    stock_max_return_pct DOUBLE NULL,
    stock_best_quality_label VARCHAR(20) NULL,
    stock_has_great TINYINT NOT NULL DEFAULT 0,
    stock_has_good_or_great TINYINT NOT NULL DEFAULT 0,
    stock_has_bad TINYINT NOT NULL DEFAULT 0,

    param_count INT NOT NULL DEFAULT 0,
    score_ge_80_param_count INT NOT NULL DEFAULT 0,
    score_ge_60_param_count INT NOT NULL DEFAULT 0,
    great_param_count INT NOT NULL DEFAULT 0,
    good_or_great_param_count INT NOT NULL DEFAULT 0,
    bad_param_count INT NOT NULL DEFAULT 0,

    best_st_period INT NULL,
    best_st_multiplier DOUBLE NULL,
    best_st_up_start_time DATETIME NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_stock_day_rank (stock_day_score_id),
    KEY ix_great_st_stock_rank_day (trade_date, rank_in_day),
    KEY ix_great_st_stock_rank_outcome (rank_in_day, stock_has_great, stock_has_good_or_great, stock_has_bad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_stock_day_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    summary_group VARCHAR(80) NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_stock_score_v1 DOUBLE NULL,
    avg_stock_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,
    avg_param_count DOUBLE NULL,
    avg_score_ge_80_param_count DOUBLE NULL,
    avg_score_ge_60_param_count DOUBLE NULL,
    avg_great_param_count DOUBLE NULL,
    avg_bad_param_count DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_stock_summary (summary_group),
    KEY ix_great_st_stock_summary_rates (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_early_stock_day_topn_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    top_n INT NOT NULL,
    day_count INT NOT NULL DEFAULT 0,
    candidate_count INT NOT NULL DEFAULT 0,
    great_hit_day_rate DOUBLE NULL,
    good_or_great_hit_day_rate DOUBLE NULL,
    bad_candidate_rate DOUBLE NULL,
    avg_top_stock_score DOUBLE NULL,
    avg_top_stock_max_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_stock_topn (top_n),
    KEY ix_great_st_stock_topn_rates (great_hit_day_rate, good_or_great_hit_day_rate, bad_candidate_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS great_st_param_confirmation_summary_v1 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    confirm_type VARCHAR(80) NOT NULL,
    confirm_value INT NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    avg_stock_score_v1 DOUBLE NULL,
    avg_stock_max_return_pct DOUBLE NULL,
    great_rate DOUBLE NULL,
    good_or_great_rate DOUBLE NULL,
    bad_rate DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_great_st_param_confirm (confirm_type, confirm_value),
    KEY ix_great_st_param_confirm_rates (great_rate, good_or_great_rate, bad_rate)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
