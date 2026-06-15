# 株式属性カタログ — 全101属性定義

## テーブル: `stocks`

| # | カラム名 | 型 | カテゴリ | 説明 | 取得方法 |
|---|---|---|---|---|---|
| **A. 基本情報 (15)** |
| 1 | stock_code | CHAR(4) | 基本 | 銘柄コード | JPX/東証 |
| 2 | isin_code | CHAR(12) | 基本 | ISINコード | JPX |
| 3 | bloomberg_ticker | VARCHAR(20) | 基本 | Bloombergティッカー | Bloomberg |
| 4 | company_name_ja | VARCHAR(100) | 基本 | 会社名 (日本語) | JPX |
| 5 | company_name_en | VARCHAR(120) | 基本 | 会社名 (英語) | JPX |
| 6 | listing_date | DATE | 基本 | 上場日 | JPX |
| 7 | is_active | BOOLEAN | 基本 | 上場中フラグ | JPX |
| 8 | headquarters_pref | VARCHAR(20) | 基本 | 本社都道府県 | EDINET |
| 9 | established_year | SMALLINT | 基本 | 設立年 | EDINET |
| 10 | employee_count | INTEGER | 基本 | 従業員数 (連結) | 有報 |
| 11 | consolidated_subs | SMALLINT | 基本 | 連結子会社数 | 有報 |
| 12 | fiscal_year_end | fiscal_month | 基本 | 決算月 | JPX |
| 13 | auditor_name | VARCHAR(60) | 基本 | 監査法人 | EDINET |
| 14 | website_url | VARCHAR(255) | 基本 | IRサイトURL | 自社 |
| 15 | ir_contact_email | VARCHAR(120) | 基本 | IRメール | 自社 |
| **B. 市場・区分情報 (12)** |
| 16 | market_section | ENUM | 市場 | Prime/Standard/Growth/TOKYO_PRO | JPX |
| 17 | is_topix | BOOLEAN | 市場 | TOPIX構成銘柄フラグ | JPX |
| 18 | topix_component | VARCHAR(20) | 市場 | Core30/Large70/Mid400/Small/Micro | JPX |
| 19 | is_nikkei225 | BOOLEAN | 市場 | 日経225構成銘柄フラグ | 日経 |
| 20 | is_jpx400 | BOOLEAN | 市場 | JPX日経400構成銘柄フラグ | JPX |
| 21 | is_msci_japan | BOOLEAN | 市場 | MSCI Japan構成銘柄フラグ | MSCI |
| 22 | is_reit | BOOLEAN | 市場 | REITフラグ | JPX |
| 23 | is_etf | BOOLEAN | 市場 | ETFフラグ | JPX |
| 24 | tradable_lots | SMALLINT | 市場 | 単元株数 | JPX |
| 25 | price_limit_type | VARCHAR(10) | 市場 | 値幅制限区分 | JPX |
| 26 | is_foreign_stock | BOOLEAN | 市場 | 外国株フラグ | JPX |
| 27 | market_open_type | VARCHAR(10) | 市場 | 連続市場/板寄せ | JPX |
| **C. 業種・分類情報 (10)** |
| 28 | industry_code | CHAR(2) | 業種 | 東証33業種コード | JPX |
| 29 | tse_size_category | ENUM | 業種 | Large/Mid/Small/Micro | JPX |
| 30 | gics_sector | VARCHAR(60) | 業種 | GICSセクター | MSCI/S&P |
| 31 | gics_industry_group | VARCHAR(60) | 業種 | GICS産業グループ | MSCI/S&P |
| 32 | gics_industry | VARCHAR(80) | 業種 | GICS産業 | MSCI/S&P |
| 33 | gics_sub_industry | VARCHAR(100) | 業種 | GICSサブ産業 | MSCI/S&P |
| 34 | sic_code | CHAR(4) | 業種 | SICコード | SEC |
| 35 | naics_code | VARCHAR(6) | 業種 | NAICSコード | 米国商務省 |
| 36 | bis_industry_code | VARCHAR(10) | 業種 | 日銀業種分類 | 日銀 |
| 37 | custom_theme_tags | TEXT[] | 業種 | 独自テーマタグ (EV/AI/半導体等) | 手動/AI |
| **D. バリュエーション (15)** |
| 38 | market_cap_jpy | BIGINT | バリュー | 時価総額 (円) | yfinance |
| 39 | shares_outstanding | BIGINT | バリュー | 発行済株式数 | yfinance |
| 40 | shares_float | BIGINT | バリュー | 浮動株数 | yfinance |
| 41 | float_ratio | NUMERIC(6,4) | バリュー | 浮動株比率 | 計算 |
| 42 | per_ttm | NUMERIC(8,2) | バリュー | PER (実績TTM) | yfinance |
| 43 | per_fwd | NUMERIC(8,2) | バリュー | PER (予想) | yfinance |
| 44 | pbr | NUMERIC(8,3) | バリュー | PBR | yfinance |
| 45 | pcfr | NUMERIC(8,2) | バリュー | PCFR | 計算 |
| 46 | psr | NUMERIC(8,3) | バリュー | PSR | 計算 |
| 47 | ev_ebitda | NUMERIC(8,2) | バリュー | EV/EBITDA | yfinance |
| 48 | ev_sales | NUMERIC(8,3) | バリュー | EV/Sales | 計算 |
| 49 | ev_ebit | NUMERIC(8,2) | バリュー | EV/EBIT | 計算 |
| 50 | earnings_yield | NUMERIC(8,4) | バリュー | 益利回り (1/PER) | 計算 |
| 51 | book_value_per_share | NUMERIC(10,2) | バリュー | BPS | yfinance |
| 52 | tangible_bvps | NUMERIC(10,2) | バリュー | 有形BPS | 計算 |
| **E. 収益性 (12)** |
| 53 | revenue_ttm_jpy | BIGINT | 収益 | 売上高 TTM | yfinance |
| 54 | operating_income_jpy | BIGINT | 収益 | 営業利益 TTM | yfinance |
| 55 | net_income_jpy | BIGINT | 収益 | 純利益 TTM | yfinance |
| 56 | eps_ttm | NUMERIC(10,2) | 収益 | EPS (実績) | yfinance |
| 57 | eps_fwd | NUMERIC(10,2) | 収益 | EPS (予想) | yfinance |
| 58 | gross_margin | NUMERIC(6,4) | 収益 | 売上総利益率 | 計算 |
| 59 | operating_margin | NUMERIC(6,4) | 収益 | 営業利益率 | 計算 |
| 60 | net_margin | NUMERIC(6,4) | 収益 | 純利益率 | 計算 |
| 61 | roe | NUMERIC(6,4) | 収益 | ROE | yfinance |
| 62 | roa | NUMERIC(6,4) | 収益 | ROA | 計算 |
| 63 | roic | NUMERIC(6,4) | 収益 | ROIC | 計算 |
| 64 | ebitda_margin | NUMERIC(6,4) | 収益 | EBITDAマージン | 計算 |
| **F. 配当・株主還元 (8)** |
| 65 | dividend_per_share | NUMERIC(8,2) | 配当 | 1株配当 (予想) | yfinance |
| 66 | dividend_yield | NUMERIC(6,4) | 配当 | 配当利回り | yfinance |
| 67 | payout_ratio | NUMERIC(6,4) | 配当 | 配当性向 | 計算 |
| 68 | is_dividend_paying | BOOLEAN | 配当 | 配当実施フラグ | 計算 |
| 69 | consecutive_div_years | SMALLINT | 配当 | 連続増配年数 | 計算 |
| 70 | buyback_yield | NUMERIC(6,4) | 配当 | 自社株買い利回り | 計算 |
| 71 | total_shareholder_yield | NUMERIC(6,4) | 配当 | 総還元利回り | 計算 |
| 72 | last_ex_dividend_date | DATE | 配当 | 直近配当落ち日 | yfinance |
| **G. 財務健全性 (8)** |
| 73 | equity_ratio | NUMERIC(6,4) | 健全性 | 自己資本比率 | 有報 |
| 74 | debt_to_equity | NUMERIC(8,3) | 健全性 | D/Eレシオ | 有報 |
| 75 | net_debt_jpy | BIGINT | 健全性 | ネットデット | 計算 |
| 76 | current_ratio | NUMERIC(6,3) | 健全性 | 流動比率 | 有報 |
| 77 | quick_ratio | NUMERIC(6,3) | 健全性 | 当座比率 | 計算 |
| 78 | interest_coverage | NUMERIC(8,2) | 健全性 | インタレストカバレッジ | 計算 |
| 79 | altman_z_score | NUMERIC(6,3) | 健全性 | Altman Zスコア | 計算 |
| 80 | credit_rating | VARCHAR(10) | 健全性 | 信用格付 | R&I/JCR |
| **H. テクニカル (12)** |
| 81 | price_latest | NUMERIC(10,2) | テクニカル | 最新株価 | yfinance |
| 82 | price_52w_high | NUMERIC(10,2) | テクニカル | 52週高値 | yfinance |
| 83 | price_52w_low | NUMERIC(10,2) | テクニカル | 52週安値 | yfinance |
| 84 | price_vs_52w_high | NUMERIC(6,4) | テクニカル | 52週高値比 | 計算 |
| 85 | rsi_14 | NUMERIC(5,2) | テクニカル | RSI (14日) | pandas-ta |
| 86 | ma25 | NUMERIC(10,2) | テクニカル | 25日移動平均 | pandas-ta |
| 87 | ma75 | NUMERIC(10,2) | テクニカル | 75日移動平均 | pandas-ta |
| 88 | ma200 | NUMERIC(10,2) | テクニカル | 200日移動平均 | pandas-ta |
| 89 | beta_1y | NUMERIC(6,3) | テクニカル | ベータ (1年) | 計算 |
| 90 | avg_volume_20d | BIGINT | テクニカル | 20日平均出来高 | 計算 |
| 91 | volume_ratio | NUMERIC(6,3) | テクニカル | 出来高比率 | 計算 |
| 92 | atr_14 | NUMERIC(10,2) | テクニカル | ATR (14日) | pandas-ta |
| **I. 株主構成 (8)** |
| 93 | foreign_ownership_ratio | NUMERIC(6,4) | 株主 | 外国人持株比率 | 有報 |
| 94 | institutional_ownership | NUMERIC(6,4) | 株主 | 機関投資家比率 | 有報 |
| 95 | insider_ownership | NUMERIC(6,4) | 株主 | 内部者持株比率 | 有報 |
| 96 | top10_holder_ratio | NUMERIC(6,4) | 株主 | 大株主上位10社合計 | 有報 |
| 97 | treasury_stock_ratio | NUMERIC(6,4) | 株主 | 自己株式比率 | 有報 |
| 98 | crossholding_ratio | NUMERIC(6,4) | 株主 | 持ち合い株比率 | 推計 |
| 99 | activist_flag | BOOLEAN | 株主 | アクティビスト関与 | 手動 |
| 100 | is_parent_listed | BOOLEAN | 株主 | 親会社上場フラグ | JPX |
| **J. ESG・ガバナンス (10)** |
| 101 | esg_score | NUMERIC(5,2) | ESG | 総合ESGスコア | MSCI/Bloomberg |
| 102 | env_score | NUMERIC(5,2) | ESG | 環境スコア | MSCI |
| 103 | social_score | NUMERIC(5,2) | ESG | 社会スコア | MSCI |
| 104 | governance_score | NUMERIC(5,2) | ESG | ガバナンススコア | MSCI |
| 105 | board_independence_ratio | NUMERIC(6,4) | ESG | 社外取締役比率 | 有報 |
| 106 | has_female_director | BOOLEAN | ESG | 女性取締役在籍フラグ | 有報 |
| 107 | co2_intensity | NUMERIC(10,3) | ESG | CO2排出強度 | CDP/有報 |
| 108 | sdgs_aligned | BOOLEAN | ESG | SDGs取組フラグ | 自社 |
| 109 | is_prime_governance | BOOLEAN | ESG | プライムガバナンス適合 | JPX |
| 110 | whistleblower_system | BOOLEAN | ESG | 内部通報制度有無 | 有報 |

---
## サテライトテーブル一覧

| テーブル名 | 用途 | 更新頻度 |
|---|---|---|
| `stock_daily_prices` | OHLCV日次履歴 | 毎営業日 |
| `stock_technical_daily` | テクニカル指標日次履歴 | 毎営業日 |
| `analyst_ratings` | アナリスト評価 | 随時 |
| `stock_news` | ニュース・センチメント | リアルタイム |
| `industry_master` | 東証33業種マスタ | 不変 |

---
## 推奨インデックス戦略

- `stocks(market_section)` — 市場区分フィルタ
- `stocks(industry_code)` — 業種フィルタ
- `stocks(is_topix) WHERE is_topix=TRUE` — TOPIXフィルタ
- `stocks(market_cap_jpy DESC)` — 時価総額ランキング
- `stocks USING GIN(custom_theme_tags)` — テーマタグ全文検索
- `stock_daily_prices(stock_code, trade_date DESC)` — 個別銘柄時系列
