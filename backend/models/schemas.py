from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class StockSummary(BaseModel):
    stock_code: str
    company_name_ja: str
    market_section: Optional[str]
    industry_code: Optional[str]
    market_cap_jpy: Optional[int]
    price_latest: Optional[Decimal]
    per_ttm: Optional[Decimal]
    pbr: Optional[Decimal]
    dividend_yield: Optional[Decimal]
    roe: Optional[Decimal]
    rsi_14: Optional[Decimal]

    model_config = {"from_attributes": True}


class StockDetail(StockSummary):
    company_name_en: Optional[str]
    listing_date: Optional[date]
    employee_count: Optional[int]
    fiscal_year_end: Optional[str]
    website_url: Optional[str]
    # バリュエーション
    per_fwd: Optional[Decimal]
    psr: Optional[Decimal]
    ev_ebitda: Optional[Decimal]
    book_value_per_share: Optional[Decimal]
    # 収益性
    revenue_ttm_jpy: Optional[int]
    operating_income_jpy: Optional[int]
    net_income_jpy: Optional[int]
    gross_margin: Optional[Decimal]
    operating_margin: Optional[Decimal]
    net_margin: Optional[Decimal]
    roa: Optional[Decimal]
    roic: Optional[Decimal]
    # 配当
    dividend_per_share: Optional[Decimal]
    payout_ratio: Optional[Decimal]
    consecutive_div_years: Optional[int]
    total_shareholder_yield: Optional[Decimal]
    # 財務健全性
    equity_ratio: Optional[Decimal]
    debt_to_equity: Optional[Decimal]
    current_ratio: Optional[Decimal]
    altman_z_score: Optional[Decimal]
    # テクニカル
    price_52w_high: Optional[Decimal]
    price_52w_low: Optional[Decimal]
    price_vs_52w_high: Optional[Decimal]
    ma25: Optional[Decimal]
    ma75: Optional[Decimal]
    ma200: Optional[Decimal]
    beta_1y: Optional[Decimal]
    # ESG
    esg_score: Optional[Decimal]
    # 株主
    foreign_ownership_ratio: Optional[Decimal]
    institutional_ownership: Optional[Decimal]
    custom_theme_tags: Optional[list[str]]


class DailyPrice(BaseModel):
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    model_config = {"from_attributes": True}


class TechnicalDaily(BaseModel):
    trade_date: date
    rsi_14: Optional[Decimal]
    macd: Optional[Decimal]
    macd_signal: Optional[Decimal]
    macd_hist: Optional[Decimal]
    bb_upper: Optional[Decimal]
    bb_mid: Optional[Decimal]
    bb_lower: Optional[Decimal]
    ma7: Optional[Decimal]
    ma25: Optional[Decimal]
    ma49: Optional[Decimal]
    ma75: Optional[Decimal]
    ma98: Optional[Decimal]
    ma200: Optional[Decimal]
    # 3σ バンド (49日)
    std_49: Optional[Decimal]
    sigma3_upper_49: Optional[Decimal]
    sigma3_lower_49: Optional[Decimal]
    is_outlier_49: Optional[bool]
    # 3σ バンド (98日)
    std_98: Optional[Decimal]
    sigma3_upper_98: Optional[Decimal]
    sigma3_lower_98: Optional[Decimal]
    is_outlier_98: Optional[bool]

    model_config = {"from_attributes": True}


class ScreeningParams(BaseModel):
    market_section: Optional[str] = None
    industry_code: Optional[str] = None
    is_topix: Optional[bool] = None
    is_nikkei225: Optional[bool] = None
    per_min: Optional[float] = None
    per_max: Optional[float] = None
    pbr_min: Optional[float] = None
    pbr_max: Optional[float] = None
    dividend_yield_min: Optional[float] = None
    roe_min: Optional[float] = None
    market_cap_min: Optional[int] = None
    market_cap_max: Optional[int] = None
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    theme_tag: Optional[str] = None
    sort_by: str = "market_cap_jpy"
    sort_order: str = "desc"
    limit: int = 50
    offset: int = 0


class ScreeningResponse(BaseModel):
    total: int
    items: list[StockSummary]


class IndustrySummary(BaseModel):
    industry_code: str
    industry_name_ja: str
    stock_count: int
    avg_roe: Optional[Decimal]
    avg_pbr: Optional[Decimal]
    avg_dividend_yield: Optional[Decimal]
    total_market_cap_jpy: Optional[int]


class DashboardSummary(BaseModel):
    total_stocks: int
    by_market: list[dict]
    by_industry: list[IndustrySummary]
    top_gainers: list[StockSummary]
    top_losers: list[StockSummary]
    high_dividend: list[StockSummary]
