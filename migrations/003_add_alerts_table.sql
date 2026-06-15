-- ============================================================
-- Migration 003: アラート設定・送信履歴テーブル
-- ============================================================

-- アラート設定 (価格・RSI の閾値をユーザーが登録)
CREATE TABLE IF NOT EXISTS alert_configs (
    id           BIGSERIAL     PRIMARY KEY,
    stock_code   CHAR(4)       NOT NULL REFERENCES stocks(stock_code),
    alert_type   VARCHAR(20)   NOT NULL,  -- 'price_above'|'price_below'|'rsi_above'|'rsi_below'
    threshold    NUMERIC(10,4) NOT NULL,  -- 価格 or RSI 値
    is_active    BOOLEAN       NOT NULL DEFAULT TRUE,
    note         TEXT,                    -- メモ (例: "目標利確ライン")
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_configs_code
    ON alert_configs (stock_code) WHERE is_active = TRUE;

-- 送信履歴 (同日・同銘柄・同種アラートの重複送信を防ぐ)
CREATE TABLE IF NOT EXISTS alert_history (
    id           BIGSERIAL     PRIMARY KEY,
    stock_code   CHAR(4),
    alert_type   VARCHAR(30)   NOT NULL,  -- 'golden_cross_7_49' 等
    trade_date   DATE          NOT NULL,
    detail       TEXT,
    sent_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- 同日・同銘柄・同アラート種別の重複挿入を禁止
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_history_dedup
    ON alert_history (stock_code, alert_type, trade_date);
