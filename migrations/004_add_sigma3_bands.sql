-- ============================================================
-- Migration 004: 3σ バンド・外れ値判定カラム追加
-- stock_technical_daily に 49日・98日の3σ統計を追加
-- ============================================================

ALTER TABLE stock_technical_daily
    -- 49日ローリング標準偏差
    ADD COLUMN IF NOT EXISTS std_49          NUMERIC(12,4),

    -- 49日 3σ バンド  (= SMA_49 ± 3 * std_49)
    ADD COLUMN IF NOT EXISTS sigma3_upper_49 NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS sigma3_lower_49 NUMERIC(12,2),

    -- 当日終値が 49日 3σ 範囲外か
    ADD COLUMN IF NOT EXISTS is_outlier_49   BOOLEAN,

    -- 98日ローリング標準偏差
    ADD COLUMN IF NOT EXISTS std_98          NUMERIC(12,4),

    -- 98日 3σ バンド  (= SMA_98 ± 3 * std_98)
    ADD COLUMN IF NOT EXISTS sigma3_upper_98 NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS sigma3_lower_98 NUMERIC(12,2),

    -- 当日終値が 98日 3σ 範囲外か
    ADD COLUMN IF NOT EXISTS is_outlier_98   BOOLEAN;
