CREATE TABLE IF NOT EXISTS wysiwyg_eval_daily_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    eval_date DATE NOT NULL,
    eligible_rows INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,

    baseline_name VARCHAR(64) NOT NULL,
    hit_at_1 INT NOT NULL DEFAULT 0,
    hit_at_3 INT NOT NULL DEFAULT 0,
    hit_at_5 INT NOT NULL DEFAULT 0,
    hit_at_10 INT NOT NULL DEFAULT 0,
    label10_rate DOUBLE NULL,
    avg_selected_max_return_pct DOUBLE NULL,
    avg_actual_top10_return_pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_wysiwyg_eval_daily (eval_date, baseline_name),
    KEY ix_wysiwyg_eval_date (eval_date),
    KEY ix_wysiwyg_eval_baseline (baseline_name),
    KEY ix_wysiwyg_eval_hit10 (hit_at_10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS wysiwyg_eval_rank_detail (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    eval_date DATE NOT NULL,
    baseline_name VARCHAR(64) NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    baseline_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,
    baseline_score DOUBLE NULL,

    capture_price DOUBLE NULL,
    max_after_price DOUBLE NULL,
    close_return_pct DOUBLE NULL,
    max_drawdown_pct DOUBLE NULL,
    base_volume BIGINT NULL,
    base_amount DOUBLE NULL,
    cum_amount_until_capture DOUBLE NULL,
    history_grade VARCHAR(30) NULL,

    in_actual_top10 TINYINT NOT NULL DEFAULT 0,
    in_baseline_top10 TINYINT NOT NULL DEFAULT 0,
    is_hit_top10 TINYINT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_wysiwyg_eval_rank (eval_date, baseline_name, code),
    KEY ix_wysiwyg_eval_rank_date_baseline (eval_date, baseline_name),
    KEY ix_wysiwyg_eval_actual_rank (actual_rank),
    KEY ix_wysiwyg_eval_baseline_rank (baseline_rank),
    KEY ix_wysiwyg_eval_hit (is_hit_top10)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
