-- ============================================================
-- Migration 002: 成長率・CF・アナリスト・空売り・需給カラム追加
-- ============================================================

ALTER TABLE stocks
    -- ── 成長率 ───────────────────────────────────────────────
    ADD COLUMN IF NOT EXISTS revenue_growth_yoy      NUMERIC(8,4),   -- 売上高成長率 YoY
    ADD COLUMN IF NOT EXISTS earnings_growth_yoy     NUMERIC(8,4),   -- 利益成長率 YoY
    ADD COLUMN IF NOT EXISTS peg_ratio               NUMERIC(8,3),   -- PEGレシオ

    -- ── キャッシュフロー・資本構造 ────────────────────────────
    ADD COLUMN IF NOT EXISTS ebitda_jpy              BIGINT,         -- EBITDA (円)
    ADD COLUMN IF NOT EXISTS free_cashflow_jpy       BIGINT,         -- フリーキャッシュフロー (円)
    ADD COLUMN IF NOT EXISTS operating_cashflow_jpy  BIGINT,         -- 営業キャッシュフロー (円)
    ADD COLUMN IF NOT EXISTS total_cash_jpy          BIGINT,         -- 現金・現金同等物 (円)
    ADD COLUMN IF NOT EXISTS total_debt_jpy          BIGINT,         -- 有利子負債合計 (円)
    ADD COLUMN IF NOT EXISTS enterprise_value_jpy    BIGINT,         -- 企業価値 EV (円)

    -- ── アナリスト評価 ────────────────────────────────────────
    ADD COLUMN IF NOT EXISTS analyst_consensus       NUMERIC(4,2),   -- 総合評価 1=強気買い〜5=売り
    ADD COLUMN IF NOT EXISTS analyst_target_price    NUMERIC(10,2),  -- 目標株価 (アナリスト平均)
    ADD COLUMN IF NOT EXISTS analyst_count           SMALLINT,       -- カバーアナリスト人数

    -- ── 空売り・需給 ─────────────────────────────────────────
    ADD COLUMN IF NOT EXISTS shares_short            BIGINT,         -- 空売り株数
    ADD COLUMN IF NOT EXISTS short_ratio             NUMERIC(6,2),   -- 空売りカバー日数
    ADD COLUMN IF NOT EXISTS short_percent_float     NUMERIC(6,4),   -- 浮動株に対する空売り比率

    -- ── 追加株価・配当指標 ────────────────────────────────────
    ADD COLUMN IF NOT EXISTS price_change_52w        NUMERIC(8,4),   -- 52週騰落率
    ADD COLUMN IF NOT EXISTS five_yr_avg_div_yield   NUMERIC(6,4),   -- 5年平均配当利回り
    ADD COLUMN IF NOT EXISTS trailing_annual_div_yield NUMERIC(6,4), -- 直近年間配当利回り
    ADD COLUMN IF NOT EXISTS consecutive_div_years_calc SMALLINT;    -- 直近連続配当年数 (yfinance履歴から計算)
