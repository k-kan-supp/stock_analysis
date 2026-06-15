# 株式属性カタログ — 全131属性定義 (stocks テーブル)

> fetch_and_populate.py で **約100属性** を yfinance + 計算値から populate。  
> `●` = yfinanceから直接取得 / `○` = 計算値 / `□` = デフォルト値 / `△` = 要外部データ

## A. 基本情報 (9属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 1 | stock_code | CHAR(4) | □ | 銘柄コード (入力値) |
| 2 | company_name_ja | VARCHAR(100) | ● | 会社名 (日本語) — longName/shortName |
| 3 | company_name_en | VARCHAR(120) | ● | 会社名 (英語) — longName |
| 4 | short_name | VARCHAR(30) | ● | 略称 — shortName |
| 5 | website_url | VARCHAR(255) | ● | IRサイトURL |
| 6 | employee_count | INTEGER | ● | 従業員数 (連結) |
| 7 | is_active | BOOLEAN | □ | 上場中フラグ (TRUE固定) |
| 8 | fiscal_year_end | fiscal_month | □ | 決算月 (デフォルト '3') |
| 9 | data_source | VARCHAR(30) | □ | データソース ('yfinance') |

*(isin_code, bloomberg_ticker, listing_date, headquarters_pref 等は要 JPX/EDINET データ)*

---

## B. 市場・区分情報 (4属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 10 | is_reit | BOOLEAN | ○ | REITフラグ (quoteType == 'REIT') |
| 11 | is_etf | BOOLEAN | ○ | ETFフラグ (quoteType == 'ETF') |
| 12 | is_foreign_stock | BOOLEAN | ○ | 外国株フラグ (country != Japan) |
| 13 | tradable_lots | SMALLINT | □ | 単元株数 (100固定) |

*(market_section, is_topix, is_nikkei225 等は要 JPX データ)*

---

## C. 業種・分類情報 (2属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 14 | gics_sector | VARCHAR(60) | ● | GICSセクター — yfinance.sector |
| 15 | gics_industry | VARCHAR(80) | ● | GICS産業 — yfinance.industry |

*(industry_code, topix_component 等は要 JPX データ)*

---

## D. バリュエーション (17属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 16 | market_cap_jpy | BIGINT | ● | 時価総額 (円) |
| 17 | shares_outstanding | BIGINT | ● | 発行済株式数 |
| 18 | shares_float | BIGINT | ● | 浮動株数 |
| 19 | float_ratio | NUMERIC(6,4) | ○ | 浮動株比率 = floatShares/sharesOutstanding |
| 20 | per_ttm | NUMERIC(8,2) | ● | PER (実績TTM) |
| 21 | per_fwd | NUMERIC(8,2) | ● | PER (予想) |
| 22 | pbr | NUMERIC(8,3) | ● | PBR |
| 23 | psr | NUMERIC(8,3) | ● | PSR |
| 24 | ev_ebitda | NUMERIC(8,2) | ● | EV/EBITDA |
| 25 | ev_sales | NUMERIC(8,3) | ● | EV/Sales |
| 26 | ev_ebit | NUMERIC(8,2) | ○ | EV/EBIT = enterpriseValue/operatingIncome |
| 27 | book_value_per_share | NUMERIC(10,2) | ● | BPS |
| 28 | tangible_bvps | NUMERIC(10,2) | ○ | 有形BPS = (equity-無形資産)/shares |
| 29 | earnings_yield | NUMERIC(8,4) | ○ | 益利回り = 1/per_ttm |
| 30 | peg_ratio | NUMERIC(8,3) | ● | PEGレシオ |
| 31 | pcfr | NUMERIC(8,2) | ○ | PCFR = marketCap/freeCashflow |
| 32 | enterprise_value_jpy | BIGINT | ● | 企業価値 EV (円) |

---

## E. 収益性 (14属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 33 | revenue_ttm_jpy | BIGINT | ● | 売上高 TTM (円) |
| 34 | operating_income_jpy | BIGINT | ○ | 営業利益 = revenue × operatingMargin |
| 35 | net_income_jpy | BIGINT | ● | 純利益 TTM (円) |
| 36 | eps_ttm | NUMERIC(10,2) | ● | EPS (実績) |
| 37 | eps_fwd | NUMERIC(10,2) | ● | EPS (予想) |
| 38 | gross_margin | NUMERIC(6,4) | ● | 売上総利益率 |
| 39 | operating_margin | NUMERIC(6,4) | ● | 営業利益率 |
| 40 | net_margin | NUMERIC(6,4) | ● | 純利益率 |
| 41 | roe | NUMERIC(6,4) | ● | ROE |
| 42 | roa | NUMERIC(6,4) | ● | ROA |
| 43 | roic | NUMERIC(6,4) | ○ | ROIC = netIncome/(equity+totalDebt) |
| 44 | ebitda_margin | NUMERIC(6,4) | ○ | EBITDAマージン = ebitda/revenue |
| 45 | revenue_growth_yoy | NUMERIC(8,4) | ● | 売上高成長率 YoY ★新規 |
| 46 | earnings_growth_yoy | NUMERIC(8,4) | ● | 利益成長率 YoY ★新規 |

---

## F. キャッシュフロー・負債 (6属性) ★新規カテゴリ

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 47 | ebitda_jpy | BIGINT | ● | EBITDA (円) ★新規 |
| 48 | free_cashflow_jpy | BIGINT | ● | フリーキャッシュフロー (円) ★新規 |
| 49 | operating_cashflow_jpy | BIGINT | ● | 営業キャッシュフロー (円) ★新規 |
| 50 | total_cash_jpy | BIGINT | ● | 現金・現金同等物 (円) ★新規 |
| 51 | total_debt_jpy | BIGINT | ● | 有利子負債合計 (円) ★新規 |
| 52 | net_debt_jpy | BIGINT | ○ | ネットデット = totalDebt - totalCash ★新規 |

---

## G. 配当・株主還元 (9属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 53 | dividend_per_share | NUMERIC(8,2) | ● | 1株配当 (予想) |
| 54 | dividend_yield | NUMERIC(6,4) | ● | 配当利回り |
| 55 | payout_ratio | NUMERIC(6,4) | ● | 配当性向 |
| 56 | is_dividend_paying | BOOLEAN | ○ | 配当実施フラグ |
| 57 | last_ex_dividend_date | DATE | ● | 直近配当落ち日 |
| 58 | five_yr_avg_div_yield | NUMERIC(6,4) | ● | 5年平均配当利回り ★新規 |
| 59 | trailing_annual_div_yield | NUMERIC(6,4) | ● | 直近年間配当利回り ★新規 |
| 60 | consecutive_div_years | SMALLINT | ○ | 連続配当年数 (配当履歴から計算) |
| 61 | total_shareholder_yield | NUMERIC(6,4) | ○ | 総還元利回り = 配当+自社株買い |

---

## H. 財務健全性 (5属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 62 | equity_ratio | NUMERIC(6,4) | ○ | 自己資本比率 = bookValue×shares/totalAssets |
| 63 | debt_to_equity | NUMERIC(8,3) | ● | D/Eレシオ |
| 64 | current_ratio | NUMERIC(6,3) | ● | 流動比率 |
| 65 | quick_ratio | NUMERIC(6,3) | ● | 当座比率 |
| 66 | interest_coverage | NUMERIC(8,2) | ○ | インタレストカバレッジ |

*(altman_z_score, credit_rating は要別途計算・外部データ)*

---

## I. テクニカル (13属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 67 | price_latest | NUMERIC(10,2) | ● | 最新株価 |
| 68 | price_52w_high | NUMERIC(10,2) | ○ | 52週高値 (1年履歴から) |
| 69 | price_52w_low | NUMERIC(10,2) | ○ | 52週安値 (1年履歴から) |
| 70 | price_vs_52w_high | NUMERIC(6,4) | ○ | 52週高値比 |
| 71 | price_change_52w | NUMERIC(8,4) | ● | 52週騰落率 ★新規 |
| 72 | rsi_14 | NUMERIC(5,2) | ○ | RSI (14日) |
| 73 | ma7 | NUMERIC(10,2) | ○ | 7日移動平均 |
| 74 | ma25 | NUMERIC(10,2) | ○ | 25日移動平均 |
| 75 | ma49 | NUMERIC(10,2) | ○ | 49日移動平均 |
| 76 | ma75 | NUMERIC(10,2) | ○ | 75日移動平均 |
| 77 | ma98 | NUMERIC(10,2) | ○ | 98日移動平均 |
| 78 | ma200 | NUMERIC(10,2) | ○ | 200日移動平均 |
| 79 | beta_1y | NUMERIC(6,3) | ○ | ベータ (vs TOPIX 1年) |
| 80 | avg_volume_20d | BIGINT | ○ | 20日平均出来高 |
| 81 | volume_ratio | NUMERIC(6,3) | ○ | 出来高比率 (当日/20日平均) |
| 82 | atr_14 | NUMERIC(10,2) | ○ | ATR (14日) |

---

## J. 株主構成 (3属性)

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 83 | foreign_ownership_ratio | NUMERIC(6,4) | ● | 外国人持株比率 (機関投資家比率で代替) |
| 84 | institutional_ownership | NUMERIC(6,4) | ● | 機関投資家持株比率 |
| 85 | insider_ownership | NUMERIC(6,4) | ● | 内部者持株比率 |

*(top10_holder_ratio, crossholding_ratio 等は要有報データ)*

---

## K. アナリスト評価 (3属性) ★新規カテゴリ

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 86 | analyst_consensus | NUMERIC(4,2) | ● | 総合評価 (1=強気買い〜5=売り) ★新規 |
| 87 | analyst_target_price | NUMERIC(10,2) | ● | 目標株価 (アナリスト平均) ★新規 |
| 88 | analyst_count | SMALLINT | ● | カバーアナリスト人数 ★新規 |

---

## L. 空売り・需給 (3属性) ★新規カテゴリ

| # | カラム名 | 型 | 取得 | 説明 |
|---|---|---|---|---|
| 89 | shares_short | BIGINT | ● | 空売り株数 ★新規 |
| 90 | short_ratio | NUMERIC(6,2) | ● | 空売りカバー日数 ★新規 |
| 91 | short_percent_float | NUMERIC(6,4) | ● | 浮動株に対する空売り比率 ★新規 |

---

## M. ESG・ガバナンス (要外部データ)

| カラム名 | 取得 | 説明 |
|---|---|---|
| esg_score | △ | 総合ESGスコア — MSCI/Bloomberg |
| env_score | △ | 環境スコア |
| social_score | △ | 社会スコア |
| governance_score | △ | ガバナンススコア |
| board_independence_ratio | △ | 社外取締役比率 — 有報 |
| has_female_director | △ | 女性取締役在籍フラグ |
| co2_intensity | △ | CO2排出強度 |

---

## populate 集計サマリ

| カテゴリ | 定義済 | populate済(yfinance) |
|---|---|---|
| A. 基本情報 | 15 | 9 |
| B. 市場・区分 | 12 | 4 |
| C. 業種・分類 | 10 | 2 |
| D. バリュエーション | 17 | 17 |
| E. 収益性 | 14 | 14 |
| F. CF・負債 ★新規 | 6 | 6 |
| G. 配当・株主還元 | 9 | 9 |
| H. 財務健全性 | 8 | 5 |
| I. テクニカル | 16 | 16 |
| J. 株主構成 | 8 | 3 |
| K. アナリスト ★新規 | 3 | 3 |
| L. 空売り・需給 ★新規 | 3 | 3 |
| M. ESG・ガバナンス | 10 | 0 (要外部データ) |
| **合計** | **131** | **91** |

> yfinance で取得できない属性 (ESG/ガバナンス/JPX固有) は別途 EDINET API・JPX CSV・有価証券報告書から補完予定。

---

## サテライトテーブル (日次 per 銘柄)

| テーブル | 属性数 | 更新頻度 |
|---|---|---|
| `stock_daily_prices` | 8 (OHLCV+adj+volume+turnover) | 毎営業日 |
| `stock_technical_daily` | 23 (MA7種+EMA2+MACD/RSI/BB/Stoch/ATR/OBV/VWAP) | 毎営業日 |
| `analyst_ratings` | 7 per レコード | 随時 |
| `stock_news` | 7 per 記事 | リアルタイム |

**1銘柄あたりの総属性数: 91 (stocks) + 23 (technical_daily) = 114属性以上**
