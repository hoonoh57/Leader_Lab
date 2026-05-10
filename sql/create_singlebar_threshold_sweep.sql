CREATE TABLE IF NOT EXISTS singlebar_threshold_sweep_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    threshold_pct DOUBLE NOT NULL,
    filter_name VARCHAR(80) NOT NULL,

    sample_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_pass_per_day DOUBLE NULL,

    actual_top1_count INT NOT NULL DEFAULT 0,
    actual_top3_count INT NOT NULL DEFAULT 0,
    actual_top5_count INT NOT NULL DEFAULT 0,
    actual_top10_count INT NOT NULL DEFAULT 0,
    hit_rate_to_actual_top10 DOUBLE NULL,

    avg_actual_max_after_return_pct DOUBLE NULL,
    median_actual_max_after_return_pct DOUBLE NULL,
    avg_break_after_max_return_pct DOUBLE NULL,
    median_break_after_max_return_pct DOUBLE NULL,
    avg_break_after_close_return_pct DOUBLE NULL,
    avg_break_after_max_drawdown_pct DOUBLE NULL,

    win_rate_after_3pct DOUBLE NULL,
    win_rate_after_5pct DOUBLE NULL,
    win_rate_after_10pct DOUBLE NULL,
    win_rate_after_20pct DOUBLE NULL,

    loss_rate_after_close_minus3pct DOUBLE NULL,
    loss_rate_after_close_minus5pct DOUBLE NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_singlebar_threshold_filter (threshold_pct, filter_name),
    KEY ix_singlebar_threshold (threshold_pct),
    KEY ix_singlebar_filter (filter_name),
    KEY ix_singlebar_pass_day (avg_pass_per_day),
    KEY ix_singlebar_win5 (win_rate_after_5pct),
    KEY ix_singlebar_loss5 (loss_rate_after_close_minus5pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
