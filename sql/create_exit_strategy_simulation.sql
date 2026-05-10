CREATE TABLE IF NOT EXISTS exit_strategy_sim_result (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    entry_filter_name VARCHAR(80) NOT NULL,
    threshold_pct DOUBLE NOT NULL,
    exit_strategy_name VARCHAR(80) NOT NULL,

    search_date DATE NOT NULL,
    search_time TIME NOT NULL,
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NULL,

    actual_rank INT NULL,
    actual_max_after_return_pct DOUBLE NULL,

    singlebar_time DATETIME NULL,
    singlebar_close_return_pct DOUBLE NULL,
    break_time DATETIME NOT NULL,
    break_price DOUBLE NOT NULL,
    break_rsi14 DOUBLE NULL,

    entry_time DATETIME NOT NULL,
    entry_price DOUBLE NOT NULL,

    exit_time DATETIME NULL,
    exit_price DOUBLE NULL,
    exit_reason VARCHAR(40) NULL,
    realized_return_pct DOUBLE NULL,

    max_profit_before_exit_pct DOUBLE NULL,
    max_drawdown_before_exit_pct DOUBLE NULL,
    holding_bars INT NULL,

    win_flag TINYINT NOT NULL DEFAULT 0,
    loss_flag TINYINT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_exit_sim_result (entry_filter_name, threshold_pct, exit_strategy_name, search_date, search_time, code),
    KEY ix_exit_sim_strategy (entry_filter_name, threshold_pct, exit_strategy_name),
    KEY ix_exit_sim_date (search_date),
    KEY ix_exit_sim_code (code),
    KEY ix_exit_sim_return (realized_return_pct),
    KEY ix_exit_sim_reason (exit_reason)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS exit_strategy_sim_summary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    entry_filter_name VARCHAR(80) NOT NULL,
    threshold_pct DOUBLE NOT NULL,
    exit_strategy_name VARCHAR(80) NOT NULL,

    sample_count INT NOT NULL DEFAULT 0,
    active_days INT NOT NULL DEFAULT 0,
    avg_trade_per_day DOUBLE NULL,

    avg_return_pct DOUBLE NULL,
    median_return_pct DOUBLE NULL,
    win_rate DOUBLE NULL,
    loss_rate DOUBLE NULL,
    profit_factor DOUBLE NULL,
    avg_win_pct DOUBLE NULL,
    avg_loss_pct DOUBLE NULL,
    max_loss_pct DOUBLE NULL,

    avg_max_profit_before_exit_pct DOUBLE NULL,
    avg_max_drawdown_before_exit_pct DOUBLE NULL,
    avg_holding_bars DOUBLE NULL,

    tp_exit_count INT NOT NULL DEFAULT 0,
    sl_exit_count INT NOT NULL DEFAULT 0,
    trailing_exit_count INT NOT NULL DEFAULT 0,
    time_exit_count INT NOT NULL DEFAULT 0,
    close_exit_count INT NOT NULL DEFAULT 0,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_exit_sim_summary (entry_filter_name, threshold_pct, exit_strategy_name),
    KEY ix_exit_sim_summary_return (avg_return_pct),
    KEY ix_exit_sim_summary_pf (profit_factor),
    KEY ix_exit_sim_summary_win (win_rate),
    KEY ix_exit_sim_summary_loss (max_loss_pct)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
