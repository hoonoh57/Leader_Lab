CREATE TABLE IF NOT EXISTS stock_info.minute5_candles (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,

    code CHAR(6) NOT NULL,
    candle_time DATETIME NOT NULL COMMENT '5분봉 기준 시간',

    open INT NOT NULL,
    high INT NOT NULL,
    low INT NOT NULL,
    close INT NOT NULL,

    volume BIGINT UNSIGNED NOT NULL DEFAULT 0,
    tramount BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '거래대금',

    source VARCHAR(30) NOT NULL DEFAULT 'server32',
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),

    UNIQUE KEY uk_m5_code_time (code, candle_time),

    KEY idx_m5_code_time (code, candle_time),
    KEY idx_m5_time (candle_time),
    KEY idx_m5_amount (code, tramount),

    CONSTRAINT fk_m5_code
        FOREIGN KEY (code)
        REFERENCES stock_info.stock_base_info(code)
        ON DELETE CASCADE
        ON UPDATE CASCADE
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci;
