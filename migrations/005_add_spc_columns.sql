-- ============================================================
-- Migration 005: SPC 管理カラム追加
-- stock_technical_daily に連続上昇/下降・Target 判定を追加
-- Target = 前日終値 × 1.005 (前日比 +0.5%)
-- Run Rule: 7 日以上同方向でフラグ
-- ============================================================

ALTER TABLE stock_technical_daily
    -- 日次リターン (前日比)
    ADD COLUMN IF NOT EXISTS daily_return              NUMERIC(10,6),
    -- 当日の Target 価格 = 前日終値 × 1.005
    ADD COLUMN IF NOT EXISTS target_price              NUMERIC(12,2),
    -- 終値が Target 以上か (daily_return >= +0.5%)
    ADD COLUMN IF NOT EXISTS is_above_target           BOOLEAN,

    -- 連続カウント (何日連続でその状態が続いているか)
    ADD COLUMN IF NOT EXISTS consecutive_rise          SMALLINT,   -- 連続上昇日数
    ADD COLUMN IF NOT EXISTS consecutive_decline       SMALLINT,   -- 連続降下日数
    ADD COLUMN IF NOT EXISTS consecutive_above_target  SMALLINT,   -- 連続 Target 以上日数
    ADD COLUMN IF NOT EXISTS consecutive_below_target  SMALLINT,   -- 連続 Target 以下日数

    -- SPC フラグ (7 日以上連続でTrue)
    ADD COLUMN IF NOT EXISTS spc_flag_run_up           BOOLEAN,    -- 連続上昇 ≥7
    ADD COLUMN IF NOT EXISTS spc_flag_run_down         BOOLEAN,    -- 連続降下 ≥7
    ADD COLUMN IF NOT EXISTS spc_flag_above_target     BOOLEAN,    -- Target 以上 ≥7 日
    ADD COLUMN IF NOT EXISTS spc_flag_below_target     BOOLEAN,    -- Target 以下 ≥7 日
    -- 上記いずれか True の場合に True
    ADD COLUMN IF NOT EXISTS spc_flag                  BOOLEAN;
