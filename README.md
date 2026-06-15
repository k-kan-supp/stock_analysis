# 株式分析アプリ (Stock Analysis)

日本株の財務・テクニカル指標を一元管理・可視化するフルスタック Web アプリケーションです。  
yfinance でデータを自動収集し、PostgreSQL に 100 属性以上を蓄積。FastAPI + React の SPA で閲覧できます。

---

## 機能概要

| 画面 | 機能 |
|---|---|
| **ダッシュボード** | 上場銘柄数・市場区分別件数・業種別時価総額 TOP10・高配当/52週高値比ランキング |
| **スクリーニング** | PER/PBR/配当利回り/ROE/RSI などで絞り込み・ソート (最大 200 件/ページ) |
| **銘柄詳細** | バリュエーション・収益性・配当・財務健全性・テクニカル・ESG を 6 タブで表示 |
| **テクニカルチャート** | ローソク足 + MA(7/49/98) + **ゴールデン/デッドクロス自動検出** + RSI + MACD |

---

## 技術スタック

```
┌─────────────────────┐   HTTP/JSON   ┌──────────────────────┐
│  Frontend (React)   │ ◄──────────► │  Backend (FastAPI)   │
│  Vite 5 / TypeScript│               │  Python 3.11+        │
│  Ant Design 5       │               │  SQLAlchemy (async)  │
│  lightweight-charts │               │  asyncpg             │
│  TanStack Query     │               └──────────┬───────────┘
└─────────────────────┘                          │ asyncpg
                                        ┌────────▼──────────┐
                                        │   PostgreSQL 15+   │
                                        │  stocks テーブル   │
                                        │  (131 カラム定義)  │
                                        └───────────────────┘
                                                 ▲
                                        ┌────────┴──────────┐
                                        │ fetch_and_populate │
                                        │  yfinance + pandas-ta │
                                        │  (毎営業日バッチ)  │
                                        └───────────────────┘
```

---

## ディレクトリ構成

```
stock_analysis/
├── schema.sql                  # DB 初期スキーマ (テーブル・インデックス・ビュー)
├── seed_industry_master.sql    # 東証33業種マスタ初期データ
├── seed_stocks_sample.sql      # サンプル銘柄データ
├── fetch_and_populate.py       # データ収集バッチ (yfinance → PostgreSQL)
├── attribute_catalog.md        # 全131属性の定義一覧
│
├── migrations/
│   ├── add_ma7_49_98.sql                    # MA7/49/98 追加
│   └── 002_add_growth_analyst_cashflow.sql  # 成長率・CF・アナリスト・空売り追加
│
├── backend/
│   ├── main.py          # FastAPI エントリーポイント・CORS 設定
│   ├── config.py        # 環境変数 (DATABASE_URL, CORS)
│   ├── requirements.txt
│   ├── db/
│   │   └── database.py  # 非同期 DB セッション管理
│   ├── models/
│   │   └── schemas.py   # Pydantic レスポンスモデル
│   └── routers/
│       ├── stocks.py     # /stocks/* (スクリーニング・詳細・価格・テクニカル)
│       ├── industries.py # /industries/
│       └── dashboard.py  # /dashboard/summary
│
└── frontend/
    ├── vite.config.ts   # Vite 設定 (/api → :8000 プロキシ)
    ├── src/
    │   ├── App.tsx                      # ルーティング定義
    │   ├── api/client.ts                # axios ラッパー (stocksApi / dashboardApi)
    │   ├── types/stock.ts               # 全 TypeScript 型定義
    │   ├── components/layout/AppLayout.tsx  # サイドバー・ヘッダー・銘柄コード検索
    │   └── pages/
    │       ├── Dashboard.tsx    # ダッシュボード
    │       ├── Screening.tsx    # スクリーニング
    │       ├── StockDetail.tsx  # 銘柄詳細 (6タブ)
    │       └── Technical.tsx    # テクニカルチャート
    └── package.json
```

---

## データベース設計

### メインテーブル: `stocks` (131 カラム)

| カテゴリ | カラム数 | 主な属性 |
|---|---|---|
| A. 基本情報 | 15 | company_name_ja, employee_count, website_url |
| B. 市場・区分 | 12 | market_section, is_topix, is_nikkei225 |
| C. 業種・分類 | 10 | industry_code, gics_sector, custom_theme_tags |
| D. バリュエーション | 17 | per_ttm/fwd, pbr, psr, ev_ebitda, peg_ratio |
| E. 収益性 | 14 | roe, roa, roic, margins, revenue/earnings_growth_yoy |
| F. CF・負債 | 6 | ebitda_jpy, free_cashflow_jpy, net_debt_jpy |
| G. 配当・株主還元 | 9 | dividend_yield, payout_ratio, consecutive_div_years |
| H. 財務健全性 | 8 | equity_ratio, debt_to_equity, altman_z_score |
| I. テクニカル | 16 | ma7/49/98/200, rsi_14, beta_1y, atr_14 |
| J. 株主構成 | 8 | foreign/institutional/insider_ownership |
| K. アナリスト評価 | 3 | analyst_consensus, analyst_target_price, analyst_count |
| L. 空売り・需給 | 3 | shares_short, short_ratio, short_percent_float |
| M. ESG・ガバナンス | 10 | esg_score, env/social/governance_score |

yfinance から約 91 属性を自動 populate します (詳細は [`attribute_catalog.md`](./attribute_catalog.md) 参照)。

### サテライトテーブル

| テーブル | 内容 | 更新頻度 |
|---|---|---|
| `stock_daily_prices` | OHLCV + 売買代金 | 毎営業日 |
| `stock_technical_daily` | MA5/7/25/49/75/98/200・EMA・MACD・RSI・BB・Stoch・ATR・OBV・VWAP (23指標) | 毎営業日 |
| `analyst_ratings` | アナリスト評価レコード | 随時 |
| `stock_news` | ニュース + センチメントスコア | リアルタイム |
| `industry_master` | 東証33業種マスタ | 不変 |

---

## API エンドポイント

| メソッド | パス | 説明 |
|---|---|---|
| GET | `/health` | ヘルスチェック |
| GET | `/api/v1/stocks/screening` | スクリーニング (クエリパラメータでフィルタ・ソート) |
| GET | `/api/v1/stocks/{code}` | 銘柄詳細 |
| GET | `/api/v1/stocks/{code}/prices` | OHLCV 日次履歴 (`?days=365`) |
| GET | `/api/v1/stocks/{code}/technicals` | テクニカル指標日次履歴 (`?days=365`) |
| GET | `/api/v1/industries/` | 業種一覧 + 統計 |
| GET | `/api/v1/dashboard/summary` | ダッシュボード集計データ |

スクリーニング主要パラメータ:

```
market_section, industry_code, is_topix, is_nikkei225
per_min/max, pbr_min/max, dividend_yield_min, roe_min
market_cap_min/max, rsi_min/max, theme_tag
sort_by (market_cap_jpy / per_ttm / pbr / ...), sort_order, limit, offset
```

---

## セットアップ手順

### 前提条件

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

### 1. データベース初期化

```bash
createdb stockdb

# スキーマ作成
psql stockdb -f schema.sql

# マイグレーション適用 (順番に実行)
psql stockdb -f migrations/add_ma7_49_98.sql
psql stockdb -f migrations/002_add_growth_analyst_cashflow.sql

# 初期データ投入
psql stockdb -f seed_industry_master.sql
psql stockdb -f seed_stocks_sample.sql      # サンプル銘柄 (任意)
```

### 2. バックエンド起動

```bash
cd backend

# 依存インストール
pip install -r requirements.txt

# 環境変数設定
cat > .env <<'EOF'
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/stockdb
CORS_ORIGINS=["http://localhost:5173"]
EOF

# 起動
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. フロントエンド起動

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173 でアクセス
```

### 4. データ収集バッチ実行

```bash
# 依存インストール
pip install yfinance pandas-ta psycopg2-binary sqlalchemy

# DEFAULT_CODES (7203, 9984, 6758 等 10 銘柄) を取得・DB 投入
DATABASE_URL=postgresql://user:pass@localhost:5432/stockdb \
  python fetch_and_populate.py

# 銘柄コードを指定して実行
DATABASE_URL=... python fetch_and_populate.py --codes 7203 9984 6758
```

バッチは 1 銘柄あたり以下を順に実行します:

1. `stocks` テーブル upsert — 約 91 属性 (yfinance + 計算値)
2. `stock_daily_prices` テーブル upsert — 1 年分 OHLCV
3. `stock_technical_daily` テーブル upsert — 1 年分 23 テクニカル指標

---

## テクニカルチャートの仕様

`/stocks/:code/technical` 画面で以下を表示します。

**ローソク足 + 移動平均線**

| 線 | 色 | 用途 |
|---|---|---|
| MA(7) | オレンジ | 短期トレンド |
| MA(49) | 紫 | 中期トレンド |
| MA(98) | 緑 | 長期トレンド |

**クロス検出ロジック**

| 種別 | 条件 | マーカー |
|---|---|---|
| ゴールデンクロス | MA7 > MA49 または MA49 > MA98 になった日 | 金色 ▲ |
| デッドクロス | MA7 < MA49 または MA49 < MA98 になった日 | 青色 ▼ |

チャート上にマーカーを打ち、直近 5 件のクロスをカード形式で一覧表示します。

**サブチャート**

- RSI(14) — 70/30 基準線つき
- MACD(12,26,9) — ライン + ヒストグラム

---

## 属性カタログ

[`attribute_catalog.md`](./attribute_catalog.md) に全 131 属性の定義・取得方法・populate 状況をまとめています。

| 記号 | 意味 |
|---|---|
| `●` | yfinance から直接取得 |
| `○` | 計算値 (例: revenue × operatingMargin) |
| `□` | 固定デフォルト値 |
| `△` | 要外部データ (EDINET / JPX / MSCI) |

---

## 今後の拡張予定

- [ ] ESG スコア・ガバナンスデータ (EDINET API 連携)
- [ ] JPX CSV による指数構成銘柄フラグ自動更新 (is_topix / is_nikkei225)
- [ ] アナリスト評価履歴テーブルへの書き込み
- [ ] ニュース取得 + LLM センチメント分析
- [ ] ゴールデン/デッドクロス発生時のプッシュ通知アラート
