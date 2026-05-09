CREATE TABLE IF NOT EXISTS stock_info.performance_result (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    search_date DATE NOT NULL COMMENT '1516 검색 기준일',
    search_time TIME NOT NULL COMMENT '1516 검색 기준시간',
    condition_name VARCHAR(100) NOT NULL DEFAULT '1516',
    hold_period VARCHAR(20) NOT NULL DEFAULT '7시간',

    code CHAR(6) NOT NULL,
    name VARCHAR(50) NOT NULL,

    ret_1m DECIMAL(8,3) NULL COMMENT '1분간 수익률',
    ret_3m DECIMAL(8,3) NULL COMMENT '3분간 수익률',
    ret_7h DECIMAL(8,3) NULL COMMENT '7시간 수익률',
    max_ret_in_period DECIMAL(8,3) NULL COMMENT '기간 내 최고수익률',

    search_volume BIGINT UNSIGNED NULL COMMENT '검색시점 거래량',
    etc_value DECIMAL(8,3) NULL,

    label_3 TINYINT(1) NOT NULL DEFAULT 0,
    label_5 TINYINT(1) NOT NULL DEFAULT 0,
    label_10 TINYINT(1) NOT NULL DEFAULT 0,

    actual_rank_by_max_ret INT NULL COMMENT '해당일 max_ret 기준 실제 순위',

    raw_line TEXT NULL,
    source_file VARCHAR(255) NULL,

    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_perf_date_time_code (
        search_date,
        search_time,
        condition_name,
        hold_period,
        code
    ),

    KEY idx_perf_date_time (search_date, search_time),
    KEY idx_perf_code_date (code, search_date),
    KEY idx_perf_max_ret (search_date, search_time, max_ret_in_period DESC),
    KEY idx_perf_label10 (label_10, search_date),
    KEY idx_perf_rank (search_date, search_time, actual_rank_by_max_ret),

    CONSTRAINT fk_perf_code
        FOREIGN KEY (code)
        REFERENCES stock_info.stock_base_info(code)
        ON DELETE CASCADE
        ON UPDATE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci;
