# 株価分析アプリ — データベース設計ドキュメント

## ファイル構成
```
stock_db/
├── schema.sql                  # DDL: テーブル/型/インデックス/ビュー定義
├── seed_industry_master.sql    # 東証33業種マスタ シードデータ
├── seed_stocks_sample.sql      # 代表5銘柄 サンプルデータ
├── fetch_and_populate.py       # yfinanceでデータ取得・DB投入スクリプト
└── attribute_catalog.md        # 属性カタログ (110属性の定義一覧)
```

## セットアップ手順

```bash
# 1. PostgreSQL にDBを作成
createdb stockdb

# 2. DDL を実行
psql stockdb < schema.sql

# 3. マスタデータを投入
psql stockdb < seed_industry_master.sql

# 4. サンプル銘柄データを投入
psql stockdb < seed_stocks_sample.sql

# 5. yfinanceで実データ取得・更新
pip install yfinance pandas-ta psycopg2-binary sqlalchemy
DATABASE_URL=postgresql://user:pass@localhost:5432/stockdb python fetch_and_populate.py
```

## スクリーニングクエリ例

```sql
-- TOPIXコア30 × PBR1倍以下 × 配当利回り3%以上
SELECT stock_code, company_name_ja, market_cap_jpy, pbr, dividend_yield
FROM v_stock_screening
WHERE topix_component = 'Core30'
  AND pbr < 1.0
  AND dividend_yield >= 0.03
ORDER BY dividend_yield DESC;

-- テーマタグ "EV" を含む銘柄
SELECT stock_code, company_name_ja, custom_theme_tags
FROM stocks
WHERE 'EV' = ANY(custom_theme_tags)
  AND market_section = 'Prime';

-- 業種別 平均ROE・PBRランキング
SELECT im.industry_name_ja, COUNT(*) AS cnt,
       ROUND(AVG(s.roe)*100, 2) AS avg_roe_pct,
       ROUND(AVG(s.pbr), 2) AS avg_pbr
FROM stocks s
JOIN industry_master im ON s.industry_code = im.industry_code
WHERE s.is_active = TRUE
GROUP BY im.industry_name_ja
ORDER BY avg_roe_pct DESC NULLS LAST;
```
