export interface StockSummary {
  stock_code: string
  company_name_ja: string
  market_section: string | null
  industry_code: string | null
  market_cap_jpy: number | null
  price_latest: number | null
  per_ttm: number | null
  pbr: number | null
  dividend_yield: number | null
  roe: number | null
  rsi_14: number | null
}

export interface StockDetail extends StockSummary {
  company_name_en: string | null
  listing_date: string | null
  employee_count: number | null
  fiscal_year_end: string | null
  website_url: string | null
  per_fwd: number | null
  psr: number | null
  ev_ebitda: number | null
  book_value_per_share: number | null
  revenue_ttm_jpy: number | null
  operating_income_jpy: number | null
  net_income_jpy: number | null
  gross_margin: number | null
  operating_margin: number | null
  net_margin: number | null
  roa: number | null
  roic: number | null
  dividend_per_share: number | null
  payout_ratio: number | null
  consecutive_div_years: number | null
  total_shareholder_yield: number | null
  equity_ratio: number | null
  debt_to_equity: number | null
  current_ratio: number | null
  altman_z_score: number | null
  price_52w_high: number | null
  price_52w_low: number | null
  price_vs_52w_high: number | null
  ma25: number | null
  ma75: number | null
  ma200: number | null
  beta_1y: number | null
  esg_score: number | null
  foreign_ownership_ratio: number | null
  institutional_ownership: number | null
  custom_theme_tags: string[] | null
}

export interface DailyPrice {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TechnicalDaily {
  trade_date: string
  rsi_14: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
  bb_upper: number | null
  bb_mid: number | null
  bb_lower: number | null
  ma7: number | null
  ma25: number | null
  ma49: number | null
  ma75: number | null
  ma98: number | null
  ma200: number | null
  // 3σ バンド (49日)
  std_49: number | null
  sigma3_upper_49: number | null
  sigma3_lower_49: number | null
  is_outlier_49: boolean | null
  // 3σ バンド (98日)
  std_98: number | null
  sigma3_upper_98: number | null
  sigma3_lower_98: number | null
  is_outlier_98: boolean | null
  // SPC 管理 (連続上昇/降下・Target 判定)
  daily_return: number | null
  target_price: number | null
  is_above_target: boolean | null
  consecutive_rise: number | null
  consecutive_decline: number | null
  consecutive_above_target: number | null
  consecutive_below_target: number | null
  spc_flag_run_up: boolean | null
  spc_flag_run_down: boolean | null
  spc_flag_above_target: boolean | null
  spc_flag_below_target: boolean | null
  spc_flag: boolean | null
}

export interface ScreeningParams {
  market_section?: string
  industry_code?: string
  is_topix?: boolean
  is_nikkei225?: boolean
  per_min?: number
  per_max?: number
  pbr_min?: number
  pbr_max?: number
  dividend_yield_min?: number
  roe_min?: number
  market_cap_min?: number
  market_cap_max?: number
  rsi_min?: number
  rsi_max?: number
  theme_tag?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export interface ScreeningResponse {
  total: number
  items: StockSummary[]
}

export interface IndustrySummary {
  industry_code: string
  industry_name_ja: string
  stock_count: number
  avg_roe: number | null
  avg_pbr: number | null
  avg_dividend_yield: number | null
  total_market_cap_jpy: number | null
}

export interface DashboardSummary {
  total_stocks: number
  by_market: Array<{ market_section: string; count: number }>
  by_industry: IndustrySummary[]
  top_gainers: StockSummary[]
  top_losers: StockSummary[]
  high_dividend: StockSummary[]
}
