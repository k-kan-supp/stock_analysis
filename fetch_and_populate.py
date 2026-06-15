"""
株価属性・OHLCV・テクニカル指標 取得・DBインサート スクリプト
yfinance + pandas-ta を使って各テーブルを一括更新する

依存: pip install yfinance pandas-ta psycopg2-binary sqlalchemy python-dotenv
環境変数 (.env または シェル変数):
  DATABASE_URL            postgresql://user:pass@localhost:5432/stockdb
  DEFAULT_FETCH_CODES     7203,9984,6758,...  (省略時は内部デフォルト10銘柄)
  FETCH_REQUEST_INTERVAL  1.5                 (Yahoo Finance レート制限対策, 省略可)
  FETCH_HISTORY_PERIOD    1y                  (属性・TOPIX 取得期間, 省略可)
  FETCH_AVG_VOLUME_WINDOW 20                  (平均出来高の計算窓, 省略可)
  FETCH_WARMUP_BUFFER_DAYS 250               (MA200 等のウォームアップ日数, 省略可)
  SPC_THRESHOLD           7                   (SPC Run Rule 連続日数閾値, 省略可)
  SPC_TARGET_RATIO        1.005               (SPC Target = 前日終値×比率, 省略可)
実行例:
  python fetch_and_populate.py
  python fetch_and_populate.py --codes 7203 9984
"""

import math
import os
import time
import logging
import argparse
from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf
import pandas_ta as ta  # noqa: F401  (DataFrame.ta 拡張のため import が必要)
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── 環境変数 ──────────────────────────────────────────────────
DB_URL = os.environ["DATABASE_URL"]
engine = create_engine(DB_URL, pool_pre_ping=True)

_default_codes_env = os.getenv("DEFAULT_FETCH_CODES", "")
DEFAULT_CODES: list[str] = (
    [c.strip() for c in _default_codes_env.split(",") if c.strip()]
    if _default_codes_env
    else ["7203", "9984", "6758", "8306", "4502", "6861", "9433", "8035", "6098", "4063"]
)

REQUEST_INTERVAL     = float(os.getenv("FETCH_REQUEST_INTERVAL",   "1.5"))
FETCH_HISTORY_PERIOD = os.getenv("FETCH_HISTORY_PERIOD",           "1y")
AVG_VOLUME_WINDOW    = int(os.getenv("FETCH_AVG_VOLUME_WINDOW",    "20"))
WARMUP_BUFFER_DAYS   = int(os.getenv("FETCH_WARMUP_BUFFER_DAYS",   "250"))
SPC_THRESHOLD        = int(os.getenv("SPC_THRESHOLD",              "7"))
SPC_TARGET_RATIO     = float(os.getenv("SPC_TARGET_RATIO",         "1.005"))

_topix_returns: Optional[pd.Series] = None  # TOPIX 日次リターンのキャッシュ


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


def safe_bool(val) -> Optional[bool]:
    """NaN / None を None に変換し、それ以外を bool に変換する。"""
    try:
        if math.isnan(float(val)):
            return None
        return bool(val)
    except (TypeError, ValueError):
        return None


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance v0.2+ の MultiIndex カラムをフラット化"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]
    return df


def _consec(cond: pd.Series) -> pd.Series:
    """連続 True 日数をカウント (False/NaN でリセット)。"""
    result: list[int] = []
    count = 0
    for val in cond:
        try:
            count = count + 1 if bool(val) else 0
        except (TypeError, ValueError):
            count = 0
        result.append(count)
    return pd.Series(result, index=cond.index, dtype="Int64")


def _count_consecutive_div_years(dividends: pd.Series) -> Optional[int]:
    """配当履歴から直近の連続配当年数を計算する"""
    if dividends.empty:
        return None
    years = sorted(dividends.index.year.unique(), reverse=True)
    if not years:
        return None
    current_year = date.today().year
    count = 0
    for y in range(current_year, current_year - 40, -1):
        if y in years:
            count += 1
        else:
            break
    return count if count > 0 else None


# ──────────────────────────────────────────────────────────
# 1. stocks テーブル UPSERT (~100 属性)
# ──────────────────────────────────────────────────────────

def fetch_stock_attributes(code: str) -> dict:  # noqa: C901
    ticker = to_ticker(code)
    t = yf.Ticker(ticker)
    info = t.info or {}

    # ── 1年分の日次履歴 (52週指標・MA・RSI・ATR) ─────────────
    hist = _flatten_columns(t.history(period=FETCH_HISTORY_PERIOD))
    price_52w_high = safe_float(hist["High"].max(), digits=2) if not hist.empty else None
    price_52w_low  = safe_float(hist["Low"].min(),  digits=2) if not hist.empty else None
    avg_vol_20d    = safe_int(hist["Volume"].tail(AVG_VOLUME_WINDOW).mean()) if len(hist) >= AVG_VOLUME_WINDOW else None

    rsi_14 = atr_14 = ma7 = ma25 = ma49 = ma75 = ma98 = ma200 = None
    price_latest = vol_ratio = None

    if not hist.empty and len(hist) >= 14:
        hist.ta.rsi(length=14, append=True)
        hist.ta.atr(length=14, append=True)
        hist.ta.sma(length=7,   append=True)
        hist.ta.sma(length=25,  append=True)
        hist.ta.sma(length=49,  append=True)
        hist.ta.sma(length=75,  append=True)
        hist.ta.sma(length=98,  append=True)
        hist.ta.sma(length=200, append=True)
        latest       = hist.iloc[-1]
        rsi_14       = safe_float(latest.get("RSI_14"),  digits=2)
        atr_14       = safe_float(latest.get("ATRr_14"), digits=2)
        ma7          = safe_float(latest.get("SMA_7"),   digits=2)
        ma25         = safe_float(latest.get("SMA_25"),  digits=2)
        ma49         = safe_float(latest.get("SMA_49"),  digits=2)
        ma75         = safe_float(latest.get("SMA_75"),  digits=2)
        ma98         = safe_float(latest.get("SMA_98"),  digits=2)
        ma200        = safe_float(latest.get("SMA_200"), digits=2)
        price_latest = safe_float(latest["Close"],       digits=2)
        vol_ratio    = (
            round(float(latest["Volume"]) / avg_vol_20d, 3)
            if avg_vol_20d else None
        )

    # ── ベータ計算 (vs TOPIX) ────────────────────────────────
    # TOPIX データはモジュールレベルでキャッシュし N 銘柄で使い回す
    global _topix_returns
    beta = None
    try:
        if _topix_returns is None:
            time.sleep(REQUEST_INTERVAL / 5)
            topix_raw      = yf.download("^TOPX", period=FETCH_HISTORY_PERIOD, progress=False)
            _topix_returns = _flatten_columns(topix_raw)["Close"].pct_change().dropna()
        stk_ret = hist["Close"].pct_change().dropna()
        aligned = pd.concat([stk_ret, _topix_returns], axis=1).dropna()
        if len(aligned) > 20:
            beta = float(aligned.cov().iloc[0, 1] / aligned.iloc[:, 1].var())
    except Exception as e:
        log.warning(f"{code}: ベータ計算失敗 — {e}")

    # ── 連続配当年数 ─────────────────────────────────────────
    consec_div = None
    try:
        divs = t.dividends
        consec_div = _count_consecutive_div_years(divs)
    except Exception:
        pass

    # ── 基本情報 ─────────────────────────────────────────────
    market_cap        = info.get("marketCap")
    price             = price_latest or safe_float(info.get("currentPrice"))
    shares_out        = info.get("sharesOutstanding")
    float_shares      = info.get("floatShares")
    total_assets      = info.get("totalAssets")
    book_value        = safe_float(info.get("bookValue"))
    revenue           = info.get("totalRevenue")
    op_margin         = safe_float(info.get("operatingMargins"))
    ebitda            = info.get("ebitda")
    free_cf           = info.get("freeCashflow")
    op_cf             = info.get("operatingCashflow")
    total_cash        = info.get("totalCash")
    total_debt        = info.get("totalDebt")
    ev                = info.get("enterpriseValue")
    net_income        = info.get("netIncomeToCommon")

    # ── 計算値 ───────────────────────────────────────────────
    float_ratio   = safe_float(float_shares / shares_out if (float_shares and shares_out) else None)
    equity_ratio  = safe_float(
        book_value * shares_out / total_assets
        if (book_value and shares_out and total_assets) else None
    )
    net_debt      = safe_int((total_debt or 0) - (total_cash or 0)) if (total_debt or total_cash) else None
    ebitda_margin = safe_float(
        float(ebitda) / float(revenue) if (ebitda and revenue) else info.get("ebitdaMargins")
    )
    # 営業利益: margin × revenue で近似 (yfinanceに直接フィールドなし)
    operating_income = safe_int(float(revenue) * float(op_margin) if (revenue and op_margin) else None)
    ev_ebit       = safe_float(float(ev) / float(operating_income) if (ev and operating_income) else None)
    pcfr          = safe_float(float(market_cap) / float(free_cf) if (market_cap and free_cf) else None)
    per_ttm       = safe_float(info.get("trailingPE"))
    earnings_yield = safe_float(1.0 / per_ttm if per_ttm else None)
    roic          = safe_float(
        float(net_income) / (float(book_value) * float(shares_out) + float(total_debt or 0))
        if (net_income and book_value and shares_out) else None
    )
    interest_cov  = safe_float(
        float(operating_income) / abs(info.get("interestExpense", 0))
        if (operating_income and info.get("interestExpense")) else None
    )
    tangible_bvps = safe_float(
        (float(book_value) * float(shares_out) - float(info.get("intangibleAssets", 0))
         - float(info.get("goodwill", 0))) / float(shares_out)
        if (book_value and shares_out) else None
    )
    div_yield     = safe_float(info.get("dividendYield"))
    buyback_yield_val = safe_float(info.get("buybackYield"))  # 利用可能なら
    total_sh_yield = safe_float(
        (div_yield or 0) + (buyback_yield_val or 0)
        if div_yield else None
    )
    price_vs_52w  = safe_float(
        float(price) / float(price_52w_high) if (price and price_52w_high) else None
    )

    # ── quoteType から is_reit / is_etf を判定 ───────────────
    quote_type    = info.get("quoteType", "")
    is_reit       = quote_type == "REIT"
    is_etf        = quote_type == "ETF"
    is_foreign    = info.get("country", "Japan") not in ("Japan", "JPN")

    # ── 組み立て ─────────────────────────────────────────────
    return dict(
        # ── A. 基本情報 ─────────────────────────────────────
        stock_code              = code,
        company_name_ja         = info.get("longName") or info.get("shortName") or code,
        company_name_en         = info.get("longName"),
        short_name              = info.get("shortName"),
        website_url             = info.get("website"),
        employee_count          = safe_int(info.get("fullTimeEmployees")),
        is_active               = True,
        fiscal_year_end         = "3",          # 日本株は3月決算が多数 (要個別補正)
        data_source             = "yfinance",

        # ── B. 市場・区分 ────────────────────────────────────
        is_reit                 = is_reit,
        is_etf                  = is_etf,
        is_foreign_stock        = is_foreign,
        tradable_lots           = 100,          # 日本株は100単元が標準

        # ── C. 業種・分類 ────────────────────────────────────
        gics_sector             = info.get("sector"),
        gics_industry           = info.get("industry"),

        # ── D. バリュエーション ──────────────────────────────
        market_cap_jpy          = safe_int(market_cap),
        shares_outstanding      = safe_int(shares_out),
        shares_float            = safe_int(float_shares),
        float_ratio             = float_ratio,
        per_ttm                 = per_ttm,
        per_fwd                 = safe_float(info.get("forwardPE")),
        pbr                     = safe_float(info.get("priceToBook"),                  digits=3),
        psr                     = safe_float(info.get("priceToSalesTrailing12Months"), digits=3),
        ev_ebitda               = safe_float(info.get("enterpriseToEbitda")),
        ev_sales                = safe_float(info.get("enterpriseToRevenue"),          digits=3),
        ev_ebit                 = ev_ebit,
        book_value_per_share    = book_value,
        tangible_bvps           = tangible_bvps,
        earnings_yield          = earnings_yield,
        peg_ratio               = safe_float(info.get("pegRatio"),                     digits=3),
        pcfr                    = pcfr,
        enterprise_value_jpy    = safe_int(ev),

        # ── E. 収益性 ────────────────────────────────────────
        revenue_ttm_jpy         = safe_int(revenue),
        operating_income_jpy    = operating_income,
        net_income_jpy          = safe_int(net_income),
        eps_ttm                 = safe_float(info.get("trailingEps")),
        eps_fwd                 = safe_float(info.get("forwardEps")),
        gross_margin            = safe_float(info.get("grossMargins")),
        operating_margin        = op_margin,
        net_margin              = safe_float(info.get("profitMargins")),
        roe                     = safe_float(info.get("returnOnEquity")),
        roa                     = safe_float(info.get("returnOnAssets")),
        roic                    = roic,
        ebitda_margin           = ebitda_margin,
        revenue_growth_yoy      = safe_float(info.get("revenueGrowth")),
        earnings_growth_yoy     = safe_float(info.get("earningsGrowth")),

        # ── CF・負債 ─────────────────────────────────────────
        ebitda_jpy              = safe_int(ebitda),
        free_cashflow_jpy       = safe_int(free_cf),
        operating_cashflow_jpy  = safe_int(op_cf),
        total_cash_jpy          = safe_int(total_cash),
        total_debt_jpy          = safe_int(total_debt),
        net_debt_jpy            = net_debt,

        # ── F. 配当・株主還元 ────────────────────────────────
        dividend_per_share      = safe_float(info.get("dividendRate")),
        dividend_yield          = div_yield,
        payout_ratio            = safe_float(info.get("payoutRatio")),
        is_dividend_paying      = bool(div_yield),
        last_ex_dividend_date   = (
            date.fromtimestamp(info["exDividendDate"])
            if info.get("exDividendDate") else None
        ),
        five_yr_avg_div_yield   = safe_float(info.get("fiveYearAvgDividendYield")),
        trailing_annual_div_yield = safe_float(info.get("trailingAnnualDividendYield")),
        consecutive_div_years   = consec_div,
        buyback_yield           = buyback_yield_val,
        total_shareholder_yield = total_sh_yield,

        # ── G. 財務健全性 ────────────────────────────────────
        equity_ratio            = equity_ratio,
        debt_to_equity          = safe_float(info.get("debtToEquity"), digits=3),
        current_ratio           = safe_float(info.get("currentRatio"), digits=3),
        quick_ratio             = safe_float(info.get("quickRatio"),   digits=3),
        interest_coverage       = interest_cov,

        # ── H. テクニカル ────────────────────────────────────
        price_latest            = price,
        price_52w_high          = price_52w_high,
        price_52w_low           = price_52w_low,
        price_vs_52w_high       = price_vs_52w,
        price_change_52w        = safe_float(info.get("52WeekChange")),
        rsi_14                  = rsi_14,
        ma7                     = ma7,
        ma25                    = ma25,
        ma49                    = ma49,
        ma75                    = ma75,
        ma98                    = ma98,
        ma200                   = ma200,
        beta_1y                 = safe_float(beta, digits=3),
        avg_volume_20d          = avg_vol_20d,
        volume_ratio            = vol_ratio,
        atr_14                  = atr_14,

        # ── I. 株主構成 ──────────────────────────────────────
        # yfinance では外国人持株比率は取得不可のため None
        foreign_ownership_ratio = None,
        institutional_ownership = safe_float(info.get("heldPercentInstitutions")),
        insider_ownership       = safe_float(info.get("heldPercentInsiders")),

        # ── アナリスト評価 ───────────────────────────────────
        analyst_consensus       = safe_float(info.get("recommendationMean"), digits=2),
        analyst_target_price    = safe_float(info.get("targetMeanPrice"),    digits=2),
        analyst_count           = safe_int(info.get("numberOfAnalystOpinions")),

        # ── 空売り・需給 ─────────────────────────────────────
        shares_short            = safe_int(info.get("sharesShort")),
        short_ratio             = safe_float(info.get("shortRatio"),         digits=2),
        short_percent_float     = safe_float(info.get("shortPercentOfFloat")),
    )


def upsert_stock(attrs: dict) -> None:
    # None 値のキーも含めて upsert (DB デフォルト/既存値を上書き)
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
    raw  = yf.download(ticker, period=f"{days}d", progress=False)
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
    raw  = yf.download(ticker, period=f"{days + WARMUP_BUFFER_DAYS}d", progress=False)
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

    # ── 3σ バンド計算 (ウォームアップ込みの全期間で計算してから tail) ──
    # μ = SMA(n), σ = rolling std(n), バンド = μ ± 3σ
    hist["STD_49"] = hist["Close"].rolling(window=49).std()
    hist["STD_98"] = hist["Close"].rolling(window=98).std()
    hist["S3U_49"] = hist["SMA_49"] + 3 * hist["STD_49"]
    hist["S3L_49"] = hist["SMA_49"] - 3 * hist["STD_49"]
    hist["S3U_98"] = hist["SMA_98"] + 3 * hist["STD_98"]
    hist["S3L_98"] = hist["SMA_98"] - 3 * hist["STD_98"]
    # 外れ値フラグ: 終値がバンド外ならTrue
    hist["OUT_49"] = (hist["Close"] > hist["S3U_49"]) | (hist["Close"] < hist["S3L_49"])
    hist["OUT_98"] = (hist["Close"] > hist["S3U_98"]) | (hist["Close"] < hist["S3L_98"])

    # ── SPC 管理 (連続上昇/降下・Target 判定) ────────────────────
    # Target = 前日終値 × SPC_TARGET_RATIO (デフォルト: 前日比 +0.5%)
    hist["PREV_CLOSE"]    = hist["Close"].shift(1)
    hist["DAILY_RET"]     = (hist["Close"] - hist["PREV_CLOSE"]) / hist["PREV_CLOSE"]
    hist["SPC_TARGET"]    = hist["PREV_CLOSE"] * SPC_TARGET_RATIO
    hist["ABOVE_TARGET"]  = hist["Close"] > hist["SPC_TARGET"]
    hist["BELOW_TARGET"]  = (hist["Close"] <= hist["SPC_TARGET"]) & hist["PREV_CLOSE"].notna()
    hist["PRICE_UP"]      = hist["Close"] > hist["PREV_CLOSE"]
    hist["PRICE_DOWN"]    = hist["Close"] < hist["PREV_CLOSE"]

    hist["CONSEC_RISE"]    = _consec(hist["PRICE_UP"])
    hist["CONSEC_DECLINE"] = _consec(hist["PRICE_DOWN"])
    hist["CONSEC_ABOVE"]   = _consec(hist["ABOVE_TARGET"])
    hist["CONSEC_BELOW"]   = _consec(hist["BELOW_TARGET"])

    hist["SPC_RUN_UP"]   = hist["CONSEC_RISE"]    >= SPC_THRESHOLD
    hist["SPC_RUN_DOWN"] = hist["CONSEC_DECLINE"] >= SPC_THRESHOLD
    hist["SPC_ABV_TGT"]  = hist["CONSEC_ABOVE"]   >= SPC_THRESHOLD
    hist["SPC_BLW_TGT"]  = hist["CONSEC_BELOW"]   >= SPC_THRESHOLD
    hist["SPC_FLAG"]     = (
        hist["SPC_RUN_UP"] | hist["SPC_RUN_DOWN"] |
        hist["SPC_ABV_TGT"] | hist["SPC_BLW_TGT"]
    )

    hist = hist.tail(days)

    rows = []
    for dt, row in hist.iterrows():
        vwap = safe_float((row["High"] + row["Low"] + row["Close"]) / 3, digits=2)
        rows.append({
            "stock_code":       code,
            "trade_date":       dt.date(),
            "ma5":              safe_float(row.get("SMA_5"),          digits=2),
            "ma7":              safe_float(row.get("SMA_7"),          digits=2),
            "ma25":             safe_float(row.get("SMA_25"),         digits=2),
            "ma49":             safe_float(row.get("SMA_49"),         digits=2),
            "ma75":             safe_float(row.get("SMA_75"),         digits=2),
            "ma98":             safe_float(row.get("SMA_98"),         digits=2),
            "ma200":            safe_float(row.get("SMA_200"),        digits=2),
            "ema12":            safe_float(row.get("EMA_12"),         digits=2),
            "ema26":            safe_float(row.get("EMA_26"),         digits=2),
            "macd":             safe_float(row.get("MACD_12_26_9"),   digits=4),
            "macd_signal":      safe_float(row.get("MACDs_12_26_9"),  digits=4),
            "macd_hist":        safe_float(row.get("MACDh_12_26_9"),  digits=4),
            "rsi_14":           safe_float(row.get("RSI_14"),         digits=2),
            "bb_upper":         safe_float(row.get("BBU_20_2.0"),     digits=2),
            "bb_mid":           safe_float(row.get("BBM_20_2.0"),     digits=2),
            "bb_lower":         safe_float(row.get("BBL_20_2.0"),     digits=2),
            "bb_width":         safe_float(row.get("BBB_20_2.0"),     digits=4),
            "stoch_k":          safe_float(row.get("STOCHk_14_3_3"),  digits=2),
            "stoch_d":          safe_float(row.get("STOCHd_14_3_3"),  digits=2),
            "atr_14":           safe_float(row.get("ATRr_14"),        digits=2),
            "obv":              safe_int(row.get("OBV")),
            "vwap":             vwap,
            # 3σ バンド
            "std_49":           safe_float(row.get("STD_49"),         digits=4),
            "sigma3_upper_49":  safe_float(row.get("S3U_49"),         digits=2),
            "sigma3_lower_49":  safe_float(row.get("S3L_49"),         digits=2),
            "is_outlier_49":    safe_bool(row.get("OUT_49")),
            "std_98":           safe_float(row.get("STD_98"),         digits=4),
            "sigma3_upper_98":  safe_float(row.get("S3U_98"),         digits=2),
            "sigma3_lower_98":  safe_float(row.get("S3L_98"),         digits=2),
            "is_outlier_98":    safe_bool(row.get("OUT_98")),
            # SPC 管理
            "daily_return":               safe_float(row.get("DAILY_RET"),    digits=6),
            "target_price":               safe_float(row.get("SPC_TARGET"),   digits=2),
            "is_above_target":            safe_bool(row.get("ABOVE_TARGET")),
            "consecutive_rise":           int(row["CONSEC_RISE"])    if pd.notna(row.get("CONSEC_RISE"))    else None,
            "consecutive_decline":        int(row["CONSEC_DECLINE"]) if pd.notna(row.get("CONSEC_DECLINE")) else None,
            "consecutive_above_target":   int(row["CONSEC_ABOVE"])   if pd.notna(row.get("CONSEC_ABOVE"))   else None,
            "consecutive_below_target":   int(row["CONSEC_BELOW"])   if pd.notna(row.get("CONSEC_BELOW"))   else None,
            "spc_flag_run_up":            safe_bool(row.get("SPC_RUN_UP")),
            "spc_flag_run_down":          safe_bool(row.get("SPC_RUN_DOWN")),
            "spc_flag_above_target":      safe_bool(row.get("SPC_ABV_TGT")),
            "spc_flag_below_target":      safe_bool(row.get("SPC_BLW_TGT")),
            "spc_flag":                   safe_bool(row.get("SPC_FLAG")),
        })

    if not rows:
        return

    sql = text("""
        INSERT INTO stock_technical_daily
            (stock_code, trade_date,
             ma5, ma7, ma25, ma49, ma75, ma98, ma200, ema12, ema26,
             macd, macd_signal, macd_hist, rsi_14,
             bb_upper, bb_mid, bb_lower, bb_width,
             stoch_k, stoch_d, atr_14, obv, vwap,
             std_49, sigma3_upper_49, sigma3_lower_49, is_outlier_49,
             std_98, sigma3_upper_98, sigma3_lower_98, is_outlier_98,
             daily_return, target_price, is_above_target,
             consecutive_rise, consecutive_decline,
             consecutive_above_target, consecutive_below_target,
             spc_flag_run_up, spc_flag_run_down,
             spc_flag_above_target, spc_flag_below_target, spc_flag)
        VALUES
            (:stock_code, :trade_date,
             :ma5, :ma7, :ma25, :ma49, :ma75, :ma98, :ma200, :ema12, :ema26,
             :macd, :macd_signal, :macd_hist, :rsi_14,
             :bb_upper, :bb_mid, :bb_lower, :bb_width,
             :stoch_k, :stoch_d, :atr_14, :obv, :vwap,
             :std_49, :sigma3_upper_49, :sigma3_lower_49, :is_outlier_49,
             :std_98, :sigma3_upper_98, :sigma3_lower_98, :is_outlier_98,
             :daily_return, :target_price, :is_above_target,
             :consecutive_rise, :consecutive_decline,
             :consecutive_above_target, :consecutive_below_target,
             :spc_flag_run_up, :spc_flag_run_down,
             :spc_flag_above_target, :spc_flag_below_target, :spc_flag)
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
            atr_14=EXCLUDED.atr_14, obv=EXCLUDED.obv, vwap=EXCLUDED.vwap,
            std_49=EXCLUDED.std_49,
            sigma3_upper_49=EXCLUDED.sigma3_upper_49,
            sigma3_lower_49=EXCLUDED.sigma3_lower_49,
            is_outlier_49=EXCLUDED.is_outlier_49,
            std_98=EXCLUDED.std_98,
            sigma3_upper_98=EXCLUDED.sigma3_upper_98,
            sigma3_lower_98=EXCLUDED.sigma3_lower_98,
            is_outlier_98=EXCLUDED.is_outlier_98,
            daily_return=EXCLUDED.daily_return,
            target_price=EXCLUDED.target_price,
            is_above_target=EXCLUDED.is_above_target,
            consecutive_rise=EXCLUDED.consecutive_rise,
            consecutive_decline=EXCLUDED.consecutive_decline,
            consecutive_above_target=EXCLUDED.consecutive_above_target,
            consecutive_below_target=EXCLUDED.consecutive_below_target,
            spc_flag_run_up=EXCLUDED.spc_flag_run_up,
            spc_flag_run_down=EXCLUDED.spc_flag_run_down,
            spc_flag_above_target=EXCLUDED.spc_flag_above_target,
            spc_flag_below_target=EXCLUDED.spc_flag_below_target,
            spc_flag=EXCLUDED.spc_flag
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
            populated = sum(1 for v in attrs.values() if v is not None)
            upsert_stock(attrs)
            log.info(f"{code}: stocks 属性 {populated}/{len(attrs)} 件 populate")
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
