"""
株価属性・OHLCV・テクニカル指標 取得・DBインサート スクリプト
yfinance + pandas-ta を使って各テーブルを一括更新する

依存: pip install yfinance pandas-ta psycopg2-binary sqlalchemy
環境変数:
  DATABASE_URL  postgresql://user:pass@localhost:5432/stockdb
実行例:
  DATABASE_URL=postgresql://... python fetch_and_populate.py
  DATABASE_URL=postgresql://... python fetch_and_populate.py --codes 7203 9984
"""

import os
import sys
import time
import logging
import argparse
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf
import pandas_ta as ta
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/stockdb")
engine = create_engine(DB_URL, pool_pre_ping=True)

DEFAULT_CODES = [
    "7203", "9984", "6758", "8306", "4502",
    "6861", "9433", "8035", "6098", "4063",
]

# Yahoo Finance へのリクエスト間隔 (秒)
REQUEST_INTERVAL = 1.5


def to_ticker(code: str) -> str:
    return f"{code}.T"


def safe_float(val, digits: int = 4, default=None) -> Optional[float]:
    try:
        f = float(val)
        return None if pd.isna(f) else round(f, digits)
    except (TypeError, ValueError):
        return default


def safe_int(val, default=None) -> Optional[int]:
    try:
        f = float(val)
        return None if pd.isna(f) else int(f)
    except (TypeError, ValueError):
        return default


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance v0.2+ の MultiIndex カラムをフラット化"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df


# ──────────────────────────────────────────────────────────
# 1. stocks テーブル UPSERT
# ──────────────────────────────────────────────────────────

def fetch_stock_attributes(code: str) -> dict:
    ticker = to_ticker(code)
    t = yf.Ticker(ticker)
    info = t.info or {}

    hist = _flatten_columns(t.history(period="1y"))
    price_52w_high = safe_float(hist["High"].max()) if not hist.empty else None
    price_52w_low  = safe_float(hist["Low"].min())  if not hist.empty else None
    avg_vol_20d    = safe_int(hist["Volume"].tail(20).mean()) if len(hist) >= 20 else None

    if not hist.empty and len(hist) >= 14:
        hist.ta.rsi(length=14, append=True)
        hist.ta.atr(length=14, append=True)
        hist.ta.sma(length=7,   append=True)
        hist.ta.sma(length=25,  append=True)
        hist.ta.sma(length=49,  append=True)
        hist.ta.sma(length=75,  append=True)
        hist.ta.sma(length=98,  append=True)
        hist.ta.sma(length=200, append=True)
        latest      = hist.iloc[-1]
        rsi_14      = safe_float(latest.get("RSI_14"))
        atr_14      = safe_float(latest.get("ATRr_14"))
        ma7         = safe_float(latest.get("SMA_7"))
        ma25        = safe_float(latest.get("SMA_25"))
        ma49        = safe_float(latest.get("SMA_49"))
        ma75        = safe_float(latest.get("SMA_75"))
        ma98        = safe_float(latest.get("SMA_98"))
        ma200       = safe_float(latest.get("SMA_200"))
        price_latest = safe_float(latest["Close"])
        vol_ratio   = (
            round(float(latest["Volume"]) / avg_vol_20d, 3)
            if avg_vol_20d else None
        )
    else:
        rsi_14 = atr_14 = ma7 = ma25 = ma49 = ma75 = ma98 = ma200 = price_latest = vol_ratio = None

    # ベータ計算 (vs TOPIX)
    try:
        time.sleep(0.5)
        topix_raw = yf.download("^TOPX", period="1y", progress=False)
        topix = _flatten_columns(topix_raw)["Close"]
        stock_ret = hist["Close"].pct_change().dropna()
        topix_ret = topix.pct_change().dropna()
        aligned = pd.concat([stock_ret, topix_ret], axis=1).dropna()
        beta = float(aligned.cov().iloc[0, 1] / aligned.iloc[:, 1].var()) if len(aligned) > 20 else None
    except Exception as e:
        log.warning(f"{code}: ベータ計算失敗 — {e}")
        beta = None

    market_cap = info.get("marketCap")
    price      = price_latest or safe_float(info.get("currentPrice"))

    shares_outstanding = info.get("sharesOutstanding")
    total_assets       = info.get("totalAssets")
    book_value         = safe_float(info.get("bookValue"))

    equity_ratio = None
    if book_value and shares_outstanding and total_assets:
        equity_ratio = safe_float(book_value * shares_outstanding / total_assets)

    return dict(
        stock_code            = code,
        company_name_ja       = info.get("longName") or info.get("shortName") or code,
        company_name_en       = info.get("longName"),
        website_url           = info.get("website"),
        employee_count        = safe_int(info.get("fullTimeEmployees")),
        # バリュエーション
        market_cap_jpy        = safe_int(market_cap),
        shares_outstanding    = safe_int(shares_outstanding),
        shares_float          = safe_int(info.get("floatShares")),
        float_ratio           = safe_float(
            info.get("floatShares", 0) / shares_outstanding
            if shares_outstanding else None
        ),
        per_ttm               = safe_float(info.get("trailingPE")),
        per_fwd               = safe_float(info.get("forwardPE")),
        pbr                   = safe_float(info.get("priceToBook"), digits=3),
        psr                   = safe_float(info.get("priceToSalesTrailing12Months"), digits=3),
        ev_ebitda             = safe_float(info.get("enterpriseToEbitda")),
        ev_sales              = safe_float(info.get("enterpriseToRevenue"), digits=3),
        book_value_per_share  = safe_float(info.get("bookValue")),
        # 収益性
        revenue_ttm_jpy       = safe_int(info.get("totalRevenue")),
        operating_income_jpy  = safe_int(info.get("operatingCashflow")),
        net_income_jpy        = safe_int(info.get("netIncomeToCommon")),
        gross_margin          = safe_float(info.get("grossMargins")),
        operating_margin      = safe_float(info.get("operatingMargins")),
        net_margin            = safe_float(info.get("profitMargins")),
        roe                   = safe_float(info.get("returnOnEquity")),
        roa                   = safe_float(info.get("returnOnAssets")),
        eps_ttm               = safe_float(info.get("trailingEps")),
        eps_fwd               = safe_float(info.get("forwardEps")),
        # 配当
        dividend_per_share    = safe_float(info.get("dividendRate")),
        dividend_yield        = safe_float(info.get("dividendYield")),
        payout_ratio          = safe_float(info.get("payoutRatio")),
        is_dividend_paying    = bool(info.get("dividendYield")),
        last_ex_dividend_date = (
            date.fromtimestamp(info["exDividendDate"])
            if info.get("exDividendDate") else None
        ),
        # 財務健全性
        equity_ratio          = equity_ratio,
        debt_to_equity        = safe_float(info.get("debtToEquity"), digits=3),
        current_ratio         = safe_float(info.get("currentRatio"), digits=3),
        quick_ratio           = safe_float(info.get("quickRatio"), digits=3),
        # テクニカル
        price_latest          = price,
        price_52w_high        = price_52w_high,
        price_52w_low         = price_52w_low,
        price_vs_52w_high     = round(float(price) / float(price_52w_high), 4)
                                if price and price_52w_high else None,
        rsi_14                = rsi_14,
        ma7                   = ma7,
        ma25                  = ma25,
        ma49                  = ma49,
        ma75                  = ma75,
        ma98                  = ma98,
        ma200                 = ma200,
        beta_1y               = safe_float(beta, digits=3),
        avg_volume_20d        = avg_vol_20d,
        volume_ratio          = vol_ratio,
        atr_14                = atr_14,
        # 株主
        foreign_ownership_ratio  = safe_float(info.get("heldPercentInstitutions")),
        institutional_ownership  = safe_float(info.get("heldPercentInstitutions")),
        insider_ownership        = safe_float(info.get("heldPercentInsiders")),
    )


def upsert_stock(attrs: dict) -> None:
    cols    = ", ".join(attrs.keys())
    vals    = ", ".join(f":{k}" for k in attrs.keys())
    updates = ", ".join(
        f"{k} = EXCLUDED.{k}" for k in attrs.keys() if k != "stock_code"
    )
    sql = text(f"""
        INSERT INTO stocks ({cols}, last_updated_at)
        VALUES ({vals}, NOW())
        ON CONFLICT (stock_code) DO UPDATE SET
            {updates},
            last_updated_at = NOW()
    """)
    with engine.begin() as conn:
        conn.execute(sql, attrs)


# ──────────────────────────────────────────────────────────
# 2. stock_daily_prices テーブル UPSERT
# ──────────────────────────────────────────────────────────

def fetch_and_store_ohlcv(code: str, days: int = 365) -> None:
    ticker = to_ticker(code)
    raw = yf.download(ticker, period=f"{days}d", progress=False)
    hist = _flatten_columns(raw)
    if hist.empty:
        log.warning(f"{code}: OHLCVデータなし")
        return

    rows = []
    for dt, row in hist.iterrows():
        rows.append({
            "stock_code": code,
            "trade_date": dt.date(),
            "open":       safe_float(row["Open"],  digits=2),
            "high":       safe_float(row["High"],  digits=2),
            "low":        safe_float(row["Low"],   digits=2),
            "close":      safe_float(row["Close"], digits=2),
            "adj_close":  safe_float(row.get("Adj Close") or row["Close"], digits=2),
            "volume":     safe_int(row["Volume"]) or 0,
        })

    sql = text("""
        INSERT INTO stock_daily_prices
            (stock_code, trade_date, open, high, low, close, adj_close, volume)
        VALUES
            (:stock_code, :trade_date, :open, :high, :low, :close, :adj_close, :volume)
        ON CONFLICT (stock_code, trade_date) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, adj_close=EXCLUDED.adj_close,
            volume=EXCLUDED.volume
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    log.info(f"{code}: {len(rows)} OHLCV rows upserted")


# ──────────────────────────────────────────────────────────
# 3. stock_technical_daily テーブル UPSERT
# ──────────────────────────────────────────────────────────

def fetch_and_store_technicals(code: str, days: int = 365) -> None:
    """全テクニカル指標を計算してstock_technical_dailyに保存。
    ウォームアップ期間 (200日MA等) のために days+250 日分取得してから末尾 days 日だけ保存する。
    """
    ticker = to_ticker(code)
    raw = yf.download(ticker, period=f"{days + 250}d", progress=False)
    hist = _flatten_columns(raw)
    if hist.empty or len(hist) < 30:
        log.warning(f"{code}: テクニカル計算に十分なデータなし")
        return

    hist.ta.sma(length=5,   append=True)
    hist.ta.sma(length=7,   append=True)
    hist.ta.sma(length=25,  append=True)
    hist.ta.sma(length=49,  append=True)
    hist.ta.sma(length=75,  append=True)
    hist.ta.sma(length=98,  append=True)
    hist.ta.sma(length=200, append=True)
    hist.ta.ema(length=12,  append=True)
    hist.ta.ema(length=26,  append=True)
    hist.ta.macd(fast=12, slow=26, signal=9, append=True)
    hist.ta.rsi(length=14, append=True)
    hist.ta.bbands(length=20, std=2, append=True)
    hist.ta.stoch(k=14, d=3, smooth_k=3, append=True)
    hist.ta.atr(length=14, append=True)
    hist.ta.obv(append=True)

    # ウォームアップ後の直近 days 行のみ保存
    hist = hist.tail(days)

    rows = []
    for dt, row in hist.iterrows():
        vwap = safe_float((row["High"] + row["Low"] + row["Close"]) / 3, digits=2)
        rows.append({
            "stock_code":   code,
            "trade_date":   dt.date(),
            "ma5":          safe_float(row.get("SMA_5"),         digits=2),
            "ma7":          safe_float(row.get("SMA_7"),         digits=2),
            "ma25":         safe_float(row.get("SMA_25"),        digits=2),
            "ma49":         safe_float(row.get("SMA_49"),        digits=2),
            "ma75":         safe_float(row.get("SMA_75"),        digits=2),
            "ma98":         safe_float(row.get("SMA_98"),        digits=2),
            "ma200":        safe_float(row.get("SMA_200"),       digits=2),
            "ema12":        safe_float(row.get("EMA_12"),        digits=2),
            "ema26":        safe_float(row.get("EMA_26"),        digits=2),
            "macd":         safe_float(row.get("MACD_12_26_9"),  digits=4),
            "macd_signal":  safe_float(row.get("MACDs_12_26_9"), digits=4),
            "macd_hist":    safe_float(row.get("MACDh_12_26_9"), digits=4),
            "rsi_14":       safe_float(row.get("RSI_14"),        digits=2),
            "bb_upper":     safe_float(row.get("BBU_20_2.0"),    digits=2),
            "bb_mid":       safe_float(row.get("BBM_20_2.0"),    digits=2),
            "bb_lower":     safe_float(row.get("BBL_20_2.0"),    digits=2),
            "bb_width":     safe_float(row.get("BBB_20_2.0"),    digits=4),
            "stoch_k":      safe_float(row.get("STOCHk_14_3_3"), digits=2),
            "stoch_d":      safe_float(row.get("STOCHd_14_3_3"), digits=2),
            "atr_14":       safe_float(row.get("ATRr_14"),       digits=2),
            "obv":          safe_int(row.get("OBV")),
            "vwap":         vwap,
        })

    if not rows:
        return

    sql = text("""
        INSERT INTO stock_technical_daily
            (stock_code, trade_date,
             ma5, ma7, ma25, ma49, ma75, ma98, ma200, ema12, ema26,
             macd, macd_signal, macd_hist, rsi_14,
             bb_upper, bb_mid, bb_lower, bb_width,
             stoch_k, stoch_d, atr_14, obv, vwap)
        VALUES
            (:stock_code, :trade_date,
             :ma5, :ma7, :ma25, :ma49, :ma75, :ma98, :ma200, :ema12, :ema26,
             :macd, :macd_signal, :macd_hist, :rsi_14,
             :bb_upper, :bb_mid, :bb_lower, :bb_width,
             :stoch_k, :stoch_d, :atr_14, :obv, :vwap)
        ON CONFLICT (stock_code, trade_date) DO UPDATE SET
            ma5=EXCLUDED.ma5, ma7=EXCLUDED.ma7,
            ma25=EXCLUDED.ma25, ma49=EXCLUDED.ma49,
            ma75=EXCLUDED.ma75, ma98=EXCLUDED.ma98, ma200=EXCLUDED.ma200,
            ema12=EXCLUDED.ema12, ema26=EXCLUDED.ema26,
            macd=EXCLUDED.macd, macd_signal=EXCLUDED.macd_signal,
            macd_hist=EXCLUDED.macd_hist, rsi_14=EXCLUDED.rsi_14,
            bb_upper=EXCLUDED.bb_upper, bb_mid=EXCLUDED.bb_mid,
            bb_lower=EXCLUDED.bb_lower, bb_width=EXCLUDED.bb_width,
            stoch_k=EXCLUDED.stoch_k, stoch_d=EXCLUDED.stoch_d,
            atr_14=EXCLUDED.atr_14, obv=EXCLUDED.obv, vwap=EXCLUDED.vwap
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    log.info(f"{code}: {len(rows)} technical rows upserted")


# ──────────────────────────────────────────────────────────
# 4. メイン処理
# ──────────────────────────────────────────────────────────

def run_all(codes: list[str]) -> None:
    success, failed = 0, []
    for i, code in enumerate(codes, 1):
        log.info(f"[{i}/{len(codes)}] Processing {code} ...")
        try:
            attrs = fetch_stock_attributes(code)
            upsert_stock(attrs)
            time.sleep(REQUEST_INTERVAL)

            fetch_and_store_ohlcv(code)
            time.sleep(REQUEST_INTERVAL)

            fetch_and_store_technicals(code)
            time.sleep(REQUEST_INTERVAL)

            log.info(f"{code}: 完了")
            success += 1
        except Exception as e:
            log.error(f"{code}: 失敗 — {e}", exc_info=True)
            failed.append(code)

    log.info(f"=== 完了: 成功 {success} 件 / 失敗 {len(failed)} 件 ===")
    if failed:
        log.warning(f"失敗銘柄: {', '.join(failed)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="株価データ取得・DB投入")
    parser.add_argument(
        "--codes", nargs="*",
        help="対象銘柄コード (省略時はDEFAULT_CODESを使用)",
    )
    args = parser.parse_args()
    target_codes = args.codes if args.codes else DEFAULT_CODES
    run_all(target_codes)
