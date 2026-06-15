-- ============================================================
-- 株価分析アプリ — 株式属性データベース スキーマ定義
-- ============================================================

-- ────────────────────────────────────────────
-- ENUM型定義
-- ────────────────────────────────────────────
CREATE TYPE market_section AS ENUM ('Prime', 'Standard', 'Growth', 'TOKYO_PRO');
CREATE TYPE size_category  AS ENUM ('Large', 'Mid', 'Small', 'Micro');
CREATE TYPE fiscal_month   AS ENUM ('3', '6', '9', '12');
CREATE TYPE rating_trend   AS ENUM ('Upgrade', 'Downgrade', 'Maintain', 'Initiate', 'Suspend');

-- ────────────────────────────────────────────
-- 1. 業種・業界マスタ
-- ────────────────────────────────────────────
CREATE TABLE industry_master (
    industry_code       CHAR(2)       PRIMARY KEY,   -- 東証33業種コード
    industry_name_ja    VARCHAR(60)   NOT NULL,
    industry_name_en    VARCHAR(80)   NOT NULL,
    sector_code         CHAR(1)       NOT NULL,       -- 大分類コード
    sector_name_ja      VARCHAR(30)   NOT NULL,
    sector_name_en      VARCHAR(40)   NOT NULL
);

-- ────────────────────────────────────────────
-- 2. 株式基本情報テーブル (1株 = 1行)
-- ────────────────────────────────────────────
CREATE TABLE stocks (
    -- [識別子]
    stock_code          CHAR(4)       PRIMARY KEY,   -- 銘柄コード (例: 7203)
    isin_code           CHAR(12)      UNIQUE,        -- ISIN (例: JP3633400001)
    bloomberg_ticker    VARCHAR(20),                  -- Bloomberg ティッカー
    reuters_ric         VARCHAR(20),                  -- Reuters RIC

    -- ────────────── A. 基本情報 (15属性) ──────────────
    company_name_ja     VARCHAR(100)  NOT NULL,
    company_name_en     VARCHAR(120),
    short_name          VARCHAR(30),
    listing_date        DATE,
    delisting_date      DATE,
    is_active           BOOLEAN       NOT NULL DEFAULT TRUE,
    website_url         VARCHAR(255),
    headquarters_pref   VARCHAR(20),                  -- 本社都道府県
    headquarters_city   VARCHAR(40),
    established_year    SMALLINT,
    employee_count      INTEGER,
    consolidated_subs   SMALLINT,                     -- 連結子会社数
    fiscal_year_end     fiscal_month  NOT NULL DEFAULT '3',
    auditor_name        VARCHAR(60),
    ir_contact_email    VARCHAR(120),

    -- ────────────── B. 市場・区分情報 (12属性) ──────────────
    market_section      market_section NOT NULL,
    is_topix            BOOLEAN       NOT NULL DEFAULT FALSE,
    topix_component     VARCHAR(20),                  -- TOPIX Core30 / Large70 / Mid400 / Small / Micro
    is_nikkei225        BOOLEAN       NOT NULL DEFAULT FALSE,
    is_jpx400           BOOLEAN       NOT NULL DEFAULT FALSE,
    is_msci_japan       BOOLEAN       NOT NULL DEFAULT FALSE,
    is_reit             BOOLEAN       NOT NULL DEFAULT FALSE,
    is_foreign_stock    BOOLEAN       NOT NULL DEFAULT FALSE,
    is_etf              BOOLEAN       NOT NULL DEFAULT FALSE,
    tradable_lots       SMALLINT      NOT NULL DEFAULT 100,  -- 単元株数
    price_limit_type    VARCHAR(10),                  -- 値幅制限区分
    market_open_type    VARCHAR(10),                  -- 連続市場 / 板寄せ

    -- ────────────── C. 業種・分類情報 (10属性) ──────────────
    industry_code       CHAR(2)       REFERENCES industry_master(industry_code),
    tse_size_category   size_category,                -- 時価総額区分
    bis_industry_code   VARCHAR(10),                  -- 日銀業種分類
    gics_sector         VARCHAR(60),                  -- GICS セクター
    gics_industry_group VARCHAR(60),
    gics_industry       VARCHAR(80),
    gics_sub_industry   VARCHAR(100),
    sic_code            CHAR(4),                      -- SIC コード
    naics_code          VARCHAR(6),                   -- NAICS コード
    custom_theme_tags   TEXT[],                       -- 独自テーマタグ (EV, AI, 半導体 等)

    -- ────────────── D. 財務指標 — バリュエーション (15属性) ──────────────
    market_cap_jpy      BIGINT,                       -- 時価総額 (円)
    shares_outstanding  BIGINT,                       -- 発行済株式数
    shares_float        BIGINT,                       -- 浮動株数
    float_ratio         NUMERIC(6,4),                 -- 浮動株比率
    per_ttm             NUMERIC(8,2),                 -- PER (実績)
    per_fwd             NUMERIC(8,2),                 -- PER (予想)
    pbr                 NUMERIC(8,3),                 -- PBR
    pcfr                NUMERIC(8,2),                 -- PCFR
    psr                 NUMERIC(8,3),                 -- PSR
    ev_ebitda           NUMERIC(8,2),                 -- EV/EBITDA
    ev_sales            NUMERIC(8,3),                 -- EV/Sales
    ev_ebit             NUMERIC(8,2),                 -- EV/EBIT
    earnings_yield      NUMERIC(8,4),                 -- 益利回り
    book_value_per_share NUMERIC(10,2),               -- BPS
    tangible_bvps       NUMERIC(10,2),                -- 有形BPS

    -- ────────────── E. 財務指標 — 収益性 (12属性) ──────────────
    revenue_ttm_jpy     BIGINT,                       -- 売上高 TTM
    operating_income_jpy BIGINT,                      -- 営業利益 TTM
    net_income_jpy      BIGINT,                       -- 純利益 TTM
    eps_ttm             NUMERIC(10,2),                -- EPS (実績)
    eps_fwd             NUMERIC(10,2),                -- EPS (予想)
    gross_margin        NUMERIC(6,4),                 -- 売上総利益率
    operating_margin    NUMERIC(6,4),                 -- 営業利益率
    net_margin          NUMERIC(6,4),                 -- 純利益率
    roe                 NUMERIC(6,4),                 -- ROE
    roa                 NUMERIC(6,4),                 -- ROA
    roic                NUMERIC(6,4),                 -- ROIC
    ebitda_margin       NUMERIC(6,4),                 -- EBITDAマージン

    -- ────────────── F. 配当・株主還元 (8属性) ──────────────
    dividend_per_share  NUMERIC(8,2),                 -- 1株配当 (予想)
    dividend_yield      NUMERIC(6,4),                 -- 配当利回り
    payout_ratio        NUMERIC(6,4),                 -- 配当性向
    is_dividend_paying  BOOLEAN       NOT NULL DEFAULT FALSE,
    consecutive_div_years SMALLINT,                   -- 連続増配年数
    buyback_yield       NUMERIC(6,4),                 -- 自社株買い利回り
    total_shareholder_yield NUMERIC(6,4),             -- 総還元利回り (配当+自社株買い)
    last_ex_dividend_date DATE,

    -- ────────────── G. 財務健全性 (8属性) ──────────────
    equity_ratio        NUMERIC(6,4),                 -- 自己資本比率
    debt_to_equity      NUMERIC(8,3),                 -- D/Eレシオ
    net_debt_jpy        BIGINT,                       -- ネットデット (円)
    current_ratio       NUMERIC(6,3),                 -- 流動比率
    quick_ratio         NUMERIC(6,3),                 -- 当座比率
    interest_coverage   NUMERIC(8,2),                 -- インタレストカバレッジ
    altman_z_score      NUMERIC(6,3),                 -- Altman Zスコア
    credit_rating       VARCHAR(10),                  -- 信用格付 (R&I / JCR 等)

    -- ────────────── H. 株価・テクニカル (12属性) ──────────────
    price_latest        NUMERIC(10,2),                -- 最新株価
    price_52w_high      NUMERIC(10,2),                -- 52週高値
    price_52w_low       NUMERIC(10,2),                -- 52週安値
    price_vs_52w_high   NUMERIC(6,4),                 -- 52週高値比
    rsi_14              NUMERIC(5,2),                 -- RSI (14日)
    ma25                NUMERIC(10,2),                -- 25日移動平均
    ma75                NUMERIC(10,2),                -- 75日移動平均
    ma200               NUMERIC(10,2),                -- 200日移動平均
    beta_1y             NUMERIC(6,3),                 -- ベータ (1年)
    avg_volume_20d      BIGINT,                       -- 20日平均出来高
    volume_ratio        NUMERIC(6,3),                 -- 出来高比率 (当日/20日平均)
    atr_14              NUMERIC(10,2),                -- ATR (14日)

    -- ────────────── I. 機関投資家・外国人持株 (8属性) ──────────────
    foreign_ownership_ratio NUMERIC(6,4),             -- 外国人持株比率
    institutional_ownership NUMERIC(6,4),             -- 機関投資家持株比率
    insider_ownership   NUMERIC(6,4),                 -- 内部者持株比率
    top10_holder_ratio  NUMERIC(6,4),                 -- 大株主上位10社合計比率
    treasury_stock_ratio NUMERIC(6,4),                -- 自己株式比率
    crossholding_ratio  NUMERIC(6,4),                 -- 持ち合い株比率
    activist_flag       BOOLEAN       NOT NULL DEFAULT FALSE,  -- アクティビスト関与フラグ
    is_parent_listed    BOOLEAN       NOT NULL DEFAULT FALSE,  -- 親会社上場フラグ

    -- ────────────── J. ESG・ガバナンス (10属性) ──────────────
    esg_score           NUMERIC(5,2),                 -- 総合ESGスコア (0-100)
    env_score           NUMERIC(5,2),                 -- 環境スコア
    social_score        NUMERIC(5,2),                 -- 社会スコア
    governance_score    NUMERIC(5,2),                 -- ガバナンススコア
    board_independence_ratio NUMERIC(6,4),            -- 社外取締役比率
    has_female_director BOOLEAN       NOT NULL DEFAULT FALSE,
    co2_intensity       NUMERIC(10,3),                -- CO2排出強度 (t-CO2/売上億円)
    sdgs_aligned        BOOLEAN,                      -- SDGs取組フラグ
    is_prime_governance BOOLEAN       NOT NULL DEFAULT FALSE,  -- プライム市場ガバナンス適合
    whistleblower_system BOOLEAN,                     -- 内部通報制度有無

    -- ────────────── メタデータ ──────────────
    data_source         VARCHAR(30)   NOT NULL DEFAULT 'yfinance',
    last_updated_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────
-- 3. 株価日次履歴テーブル (OHLCV)
-- ────────────────────────────────────────────
CREATE TABLE stock_daily_prices (
    stock_code      CHAR(4)       NOT NULL REFERENCES stocks(stock_code),
    trade_date      DATE          NOT NULL,
    open            NUMERIC(10,2) NOT NULL,
    high            NUMERIC(10,2) NOT NULL,
    low             NUMERIC(10,2) NOT NULL,
    close           NUMERIC(10,2) NOT NULL,
    adj_close       NUMERIC(10,2) NOT NULL,
    volume          BIGINT        NOT NULL,
    turnover_jpy    BIGINT,                   -- 売買代金 (円)
    PRIMARY KEY (stock_code, trade_date)
);

-- ────────────────────────────────────────────
-- 4. テクニカル指標履歴テーブル
-- ────────────────────────────────────────────
CREATE TABLE stock_technical_daily (
    stock_code      CHAR(4)       NOT NULL REFERENCES stocks(stock_code),
    trade_date      DATE          NOT NULL,
    ma5             NUMERIC(10,2),
    ma25            NUMERIC(10,2),
    ma75            NUMERIC(10,2),
    ma200           NUMERIC(10,2),
    ema12           NUMERIC(10,2),
    ema26           NUMERIC(10,2),
    macd            NUMERIC(10,4),
    macd_signal     NUMERIC(10,4),
    macd_hist       NUMERIC(10,4),
    rsi_14          NUMERIC(5,2),
    bb_upper        NUMERIC(10,2),
    bb_mid          NUMERIC(10,2),
    bb_lower        NUMERIC(10,2),
    bb_width        NUMERIC(8,4),
    stoch_k         NUMERIC(5,2),
    stoch_d         NUMERIC(5,2),
    atr_14          NUMERIC(10,2),
    obv             BIGINT,
    vwap            NUMERIC(10,2),
    PRIMARY KEY (stock_code, trade_date)
);

-- ────────────────────────────────────────────
-- 5. アナリスト評価テーブル
-- ────────────────────────────────────────────
CREATE TABLE analyst_ratings (
    id              BIGSERIAL     PRIMARY KEY,
    stock_code      CHAR(4)       NOT NULL REFERENCES stocks(stock_code),
    rating_date     DATE          NOT NULL,
    analyst_firm    VARCHAR(60)   NOT NULL,
    analyst_name    VARCHAR(60),
    rating          VARCHAR(20)   NOT NULL,   -- 買い / 中立 / 売り / 強気買い 等
    trend           rating_trend,
    target_price    NUMERIC(10,2),
    previous_target NUMERIC(10,2),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────
-- 6. ニュース・センチメントテーブル
-- ────────────────────────────────────────────
CREATE TABLE stock_news (
    id              BIGSERIAL     PRIMARY KEY,
    stock_code      CHAR(4)       REFERENCES stocks(stock_code),
    published_at    TIMESTAMPTZ   NOT NULL,
    source          VARCHAR(60)   NOT NULL,
    headline        TEXT          NOT NULL,
    url             TEXT,
    sentiment_score NUMERIC(4,3),            -- -1.0 (悲観) 〜 +1.0 (楽観)
    sentiment_label VARCHAR(10),             -- positive / neutral / negative
    llm_summary     TEXT,                    -- AI要約
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────
-- インデックス
-- ────────────────────────────────────────────
CREATE INDEX idx_stocks_market_section   ON stocks(market_section);
CREATE INDEX idx_stocks_industry         ON stocks(industry_code);
CREATE INDEX idx_stocks_topix            ON stocks(is_topix) WHERE is_topix = TRUE;
CREATE INDEX idx_stocks_nikkei           ON stocks(is_nikkei225) WHERE is_nikkei225 = TRUE;
CREATE INDEX idx_stocks_market_cap       ON stocks(market_cap_jpy DESC NULLS LAST);
CREATE INDEX idx_stocks_active           ON stocks(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_stocks_gics_sector      ON stocks(gics_sector);
CREATE INDEX idx_stocks_theme_tags       ON stocks USING GIN(custom_theme_tags);
CREATE INDEX idx_daily_prices_date       ON stock_daily_prices(trade_date DESC);
CREATE INDEX idx_daily_prices_code_date  ON stock_daily_prices(stock_code, trade_date DESC);
CREATE INDEX idx_technical_code_date     ON stock_technical_daily(stock_code, trade_date DESC);
CREATE INDEX idx_analyst_code_date       ON analyst_ratings(stock_code, rating_date DESC);
CREATE INDEX idx_news_code_published     ON stock_news(stock_code, published_at DESC);
CREATE INDEX idx_news_sentiment          ON stock_news(sentiment_score);

-- ────────────────────────────────────────────
-- 便利ビュー: スクリーニング用フラット集計
-- ────────────────────────────────────────────
CREATE VIEW v_stock_screening AS
SELECT
    s.stock_code,
    s.company_name_ja,
    s.market_section,
    s.is_topix,
    s.topix_component,
    s.is_nikkei225,
    s.is_jpx400,
    im.industry_name_ja     AS industry,
    im.sector_name_ja       AS sector,
    s.gics_sector,
    s.tse_size_category,
    s.custom_theme_tags,
    s.market_cap_jpy,
    s.per_ttm,
    s.per_fwd,
    s.pbr,
    s.ev_ebitda,
    s.dividend_yield,
    s.payout_ratio,
    s.consecutive_div_years,
    s.roe,
    s.roa,
    s.roic,
    s.operating_margin,
    s.net_margin,
    s.equity_ratio,
    s.debt_to_equity,
    s.altman_z_score,
    s.rsi_14,
    s.beta_1y,
    s.price_vs_52w_high,
    s.foreign_ownership_ratio,
    s.esg_score,
    s.governance_score,
    s.last_updated_at
FROM stocks s
LEFT JOIN industry_master im ON s.industry_code = im.industry_code
WHERE s.is_active = TRUE;

