"""
株式アラート通知スクリプト — Outlook SMTP 版

対応アラート:
  1. ゴールデン/デッドクロス  (MA7×MA49, MA49×MA98)
  2. 価格アラート             (alert_configs テーブルで設定)
  3. RSI 過熱/売られすぎ      (デフォルト 70超 / 30割れ)
  4. SPC 管理アラート         (7日以上の連続上昇/降下/Target超え/未達)
  5. 毎朝サマリーレポート      (ウォッチリスト銘柄の状況一覧)

必要パッケージ:
  pip install sqlalchemy psycopg2-binary python-dotenv

環境変数 (.env または シェル変数):
  DATABASE_URL      postgresql://user:pass@localhost:5432/stockdb
  SMTP_HOST         smtp.office365.com          (省略可: デフォルト値あり)
  SMTP_PORT         587                         (省略可)
  SMTP_USER         your@outlook.com            (送信元アドレス)
  SMTP_PASSWORD     xxxxxxxxx                   (パスワード or アプリパスワード)
  NOTIFY_TO         dest@example.com            (送信先、カンマ区切りで複数可)
  WATCHLIST_CODES   7203,9984,6758              (省略時 = DB の全アクティブ銘柄)
  RSI_HIGH          70                          (省略可)
  RSI_LOW           30                          (省略可)

実行例:
  python notify.py                   # 全アラート一括チェック
  python notify.py --mode cross      # クロス検出のみ
  python notify.py --mode price      # 価格アラートのみ
  python notify.py --mode rsi        # RSI アラートのみ
  python notify.py --mode spc        # SPC アラートのみ
  python notify.py --mode report     # 朝次サマリーレポートのみ
  python notify.py --dry-run         # メール送信せずログ出力だけ確認
"""

from __future__ import annotations

import argparse
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── 環境変数 ──────────────────────────────────────────────────
DB_URL    = os.environ["DATABASE_URL"]
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.office365.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASSWORD"]
NOTIFY_TO = [e.strip() for e in os.getenv("NOTIFY_TO", SMTP_USER).split(",") if e.strip()]
WATCHLIST              = [c.strip() for c in os.getenv("WATCHLIST_CODES", "").split(",") if c.strip()]
RSI_HIGH               = float(os.getenv("RSI_HIGH",                "70"))
RSI_LOW                = float(os.getenv("RSI_LOW",                 "30"))
SPC_THRESHOLD          = int(os.getenv("SPC_THRESHOLD",             "7"))
SPC_TARGET_RATIO       = float(os.getenv("SPC_TARGET_RATIO",        "1.005"))
VOLUME_SURGE_THRESHOLD = float(os.getenv("VOLUME_SURGE_THRESHOLD",  "3.0"))
DIVIDEND_ALERT_DAYS    = int(os.getenv("DIVIDEND_ALERT_DAYS",       "14"))

engine = create_engine(DB_URL, pool_pre_ping=True)
TODAY  = date.today()


# ══════════════════════════════════════════════════════════════
# メール送信
# ══════════════════════════════════════════════════════════════

def send_email(subject: str, html_body: str, dry_run: bool = False) -> None:
    """Outlook SMTP (STARTTLS / Port 587) でメールを送信する。"""
    if dry_run:
        log.info(f"[DRY-RUN] 件名: {subject}")
        log.info(f"[DRY-RUN] 送信先: {NOTIFY_TO}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = ", ".join(NOTIFY_TO)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(SMTP_USER, NOTIFY_TO, msg.as_string())

    log.info(f"送信完了: {subject} → {NOTIFY_TO}")


# ══════════════════════════════════════════════════════════════
# アラート履歴 (重複送信防止)
# ══════════════════════════════════════════════════════════════

def _already_sent(code: Optional[str], alert_type: str, trade_date: date) -> bool:
    """同日・同銘柄・同種アラートが既に送信済みかどうか確認する。"""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT 1 FROM alert_history
                WHERE stock_code IS NOT DISTINCT FROM :code
                  AND alert_type  = :atype
                  AND trade_date  = :dt
                LIMIT 1
            """),
            {"code": code, "atype": alert_type, "dt": trade_date},
        ).fetchone()
    return row is not None


def _record_sent(code: Optional[str], alert_type: str, trade_date: date, detail: str) -> None:
    """送信済みとして記録する。UNIQUE 制約違反 (既存) は無視する。"""
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO alert_history (stock_code, alert_type, trade_date, detail)
                VALUES (:code, :atype, :dt, :detail)
                ON CONFLICT (stock_code, alert_type, trade_date) DO NOTHING
            """),
            {"code": code, "atype": alert_type, "dt": trade_date, "detail": detail},
        )


# ══════════════════════════════════════════════════════════════
# 1. ゴールデン/デッドクロス検出
# ══════════════════════════════════════════════════════════════

_CROSS_PAIRS = [("ma7", "ma49", "7/49"), ("ma49", "ma98", "49/98")]

_CROSS_ROW_SQL = text("""
    SELECT stock_code, trade_date, ma7, ma49, ma98
    FROM stock_technical_daily
    WHERE stock_code = :code
      AND ma7  IS NOT NULL
      AND ma49 IS NOT NULL
      AND ma98 IS NOT NULL
    ORDER BY trade_date DESC
    LIMIT 2
""")


def check_crosses(dry_run: bool = False) -> list[dict]:
    """直近2営業日の MA を比較してクロスを検出し、未送信分をメール送信する。"""
    with engine.connect() as conn:
        if WATCHLIST:
            codes = WATCHLIST
        else:
            codes = [r[0] for r in conn.execute(
                text("SELECT stock_code FROM stocks WHERE is_active = TRUE")
            ).fetchall()]

    detected: list[dict] = []

    with engine.connect() as conn:
        for code in codes:
            rows = conn.execute(_CROSS_ROW_SQL, {"code": code}).fetchall()
            if len(rows) < 2:
                continue

            curr, prev = rows[0], rows[1]
            curr_vals = {"ma7": curr.ma7, "ma49": curr.ma49, "ma98": curr.ma98}
            prev_vals = {"ma7": prev.ma7, "ma49": prev.ma49, "ma98": prev.ma98}

            for short_key, long_key, label in _CROSS_PAIRS:
                cs, cl = float(curr_vals[short_key]), float(curr_vals[long_key])
                ps, pl = float(prev_vals[short_key]), float(prev_vals[long_key])

                cross_type = None
                if ps < pl and cs >= cl:
                    cross_type = "golden"
                elif ps > pl and cs <= cl:
                    cross_type = "dead"

                if cross_type is None:
                    continue

                alert_key = f"{cross_type}_cross_{label.replace('/', '_')}"
                if _already_sent(code, alert_key, curr.trade_date):
                    continue

                name = _get_name(code, conn)
                detected.append({
                    "code": code, "name": name,
                    "type": cross_type, "pair": label,
                    "date": curr.trade_date, "alert_key": alert_key,
                    "short_val": cs, "long_val": cl,
                })

    if not detected:
        log.info("クロス: 新規アラートなし")
        return []

    # メール送信
    golden = [d for d in detected if d["type"] == "golden"]
    dead   = [d for d in detected if d["type"] == "dead"]

    rows_html = "".join(
        f"<tr style='background:{'#fff8f0' if d['type']=='golden' else '#f0f4ff'}'>"
        f"<td>{d['code']}</td><td>{d['name']}</td>"
        f"<td>{'🟡 ゴールデンクロス' if d['type']=='golden' else '🔵 デッドクロス'}</td>"
        f"<td>MA({d['pair']})</td>"
        f"<td>{d['short_val']:.0f} / {d['long_val']:.0f}</td>"
        f"<td>{d['date']}</td></tr>"
        for d in detected
    )

    html = _wrap_html(
        f"クロスアラート: ゴールデン {len(golden)} 件 / デッドクロス {len(dead)} 件",
        f"""
        <h2>クロス検出アラート ({TODAY})</h2>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
          <thead style="background:#f5f5f5">
            <tr><th>コード</th><th>銘柄名</th><th>種別</th><th>ペア</th>
                <th>短期/長期 MA</th><th>日付</th></tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        """,
    )

    subject = f"【株式アラート】クロス検出 {TODAY} (G:{len(golden)} D:{len(dead)})"
    send_email(subject, html, dry_run)

    if not dry_run:
        with engine.begin() as conn:
            for d in detected:
                _record_sent(d["code"], d["alert_key"], d["date"],
                             f"{d['type']} MA{d['pair']} {d['short_val']:.0f}/{d['long_val']:.0f}")

    return detected


# ══════════════════════════════════════════════════════════════
# 2. 価格アラート
# ══════════════════════════════════════════════════════════════

def check_price_alerts(dry_run: bool = False) -> list[dict]:
    """alert_configs テーブルの設定と現在株価を照合してアラートを送信する。"""
    sql = text("""
        SELECT ac.id, ac.stock_code, s.company_name_ja,
               ac.alert_type, ac.threshold, s.price_latest, ac.note
        FROM alert_configs ac
        JOIN stocks s ON s.stock_code = ac.stock_code
        WHERE ac.is_active = TRUE
          AND ac.alert_type IN ('price_above', 'price_below')
          AND s.price_latest IS NOT NULL
    """)

    with engine.connect() as conn:
        configs = conn.execute(sql).mappings().fetchall()

    triggered: list[dict] = []
    for cfg in configs:
        price = float(cfg["price_latest"])
        thr   = float(cfg["threshold"])
        hit   = (cfg["alert_type"] == "price_above" and price >= thr) or \
                (cfg["alert_type"] == "price_below" and price <= thr)
        if not hit:
            continue

        label = "price_above" if cfg["alert_type"] == "price_above" else "price_below"
        if _already_sent(cfg["stock_code"], f"{label}_{thr:.0f}", TODAY):
            continue

        triggered.append({**dict(cfg), "current_price": price, "alert_key": f"{label}_{thr:.0f}"})

    if not triggered:
        log.info("価格アラート: 新規アラートなし")
        return []

    rows_html = "".join(
        f"<tr><td>{t['stock_code']}</td><td>{t['company_name_ja']}</td>"
        f"<td>{'↑ 上限突破' if t['alert_type']=='price_above' else '↓ 下限割れ'}</td>"
        f"<td style='text-align:right'>¥{t['threshold']:,.0f}</td>"
        f"<td style='text-align:right'><b>¥{t['current_price']:,.0f}</b></td>"
        f"<td>{t.get('note') or ''}</td></tr>"
        for t in triggered
    )

    html = _wrap_html(
        f"価格アラート {len(triggered)} 件",
        f"""
        <h2>価格アラート ({TODAY})</h2>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
          <thead style="background:#f5f5f5">
            <tr><th>コード</th><th>銘柄名</th><th>種別</th><th>設定価格</th><th>現在値</th><th>メモ</th></tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        """,
    )

    send_email(f"【株式アラート】価格アラート {TODAY} ({len(triggered)} 件)", html, dry_run)

    if not dry_run:
        for t in triggered:
            _record_sent(t["stock_code"], t["alert_key"], TODAY,
                         f"{t['alert_type']} thr={t['threshold']} price={t['current_price']}")

    return triggered


# ══════════════════════════════════════════════════════════════
# 3. RSI 過熱 / 売られすぎアラート
# ══════════════════════════════════════════════════════════════

def check_rsi_alerts(dry_run: bool = False) -> list[dict]:
    """RSI が RSI_HIGH 超または RSI_LOW 割れの銘柄を検出して通知する。"""
    codes_filter = (
        "AND s.stock_code = ANY(:codes)"
        if WATCHLIST else ""
    )
    sql = text(f"""
        SELECT s.stock_code, s.company_name_ja, s.rsi_14, s.price_latest
        FROM stocks s
        WHERE s.is_active = TRUE
          AND s.rsi_14 IS NOT NULL
          AND (s.rsi_14 >= :high OR s.rsi_14 <= :low)
          {codes_filter}
        ORDER BY s.rsi_14 DESC
    """)
    params: dict = {"high": RSI_HIGH, "low": RSI_LOW}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    triggered: list[dict] = []
    for r in rows:
        rsi   = float(r["rsi_14"])
        label = "rsi_above" if rsi >= RSI_HIGH else "rsi_below"
        if _already_sent(r["stock_code"], label, TODAY):
            continue
        triggered.append({**dict(r), "rsi": rsi, "alert_key": label})

    if not triggered:
        log.info("RSI アラート: 新規アラートなし")
        return []

    over  = [t for t in triggered if t["rsi"] >= RSI_HIGH]
    under = [t for t in triggered if t["rsi"] <  RSI_HIGH]

    def rsi_row(t: dict) -> str:
        color = "#fff0f0" if t["rsi"] >= RSI_HIGH else "#f0f0ff"
        badge = f"🔴 過熱 ({RSI_HIGH}超)" if t["rsi"] >= RSI_HIGH else f"🔵 売られすぎ ({RSI_LOW}割れ)"
        return (
            f"<tr style='background:{color}'>"
            f"<td>{t['stock_code']}</td><td>{t['company_name_ja']}</td>"
            f"<td>{badge}</td>"
            f"<td style='text-align:right'><b>{t['rsi']:.1f}</b></td>"
            f"<td style='text-align:right'>¥{float(t['price_latest']):,.0f}</td></tr>"
        )

    html = _wrap_html(
        f"RSI アラート {len(triggered)} 件",
        f"""
        <h2>RSI アラート ({TODAY})</h2>
        <p>基準値: 過熱 ≥ {RSI_HIGH} / 売られすぎ ≤ {RSI_LOW}</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%">
          <thead style="background:#f5f5f5">
            <tr><th>コード</th><th>銘柄名</th><th>状態</th><th>RSI(14)</th><th>現在値</th></tr>
          </thead>
          <tbody>{"".join(rsi_row(t) for t in triggered)}</tbody>
        </table>
        """,
    )

    send_email(
        f"【株式アラート】RSI {TODAY} (過熱:{len(over)} 売られすぎ:{len(under)})",
        html, dry_run,
    )

    if not dry_run:
        for t in triggered:
            _record_sent(t["stock_code"], t["alert_key"], TODAY, f"RSI={t['rsi']:.1f}")

    return triggered


# ══════════════════════════════════════════════════════════════
# 4. SPC 管理アラート
# ══════════════════════════════════════════════════════════════

_SPC_RULE_CHECKS = [
    ("spc_flag_run_up",       "spc_run_up",       "連続上昇",   "consecutive_rise"),
    ("spc_flag_run_down",     "spc_run_down",      "連続降下",   "consecutive_decline"),
    ("spc_flag_above_target", "spc_above_target",  "Target超え", "consecutive_above_target"),
    ("spc_flag_below_target", "spc_below_target",  "Target未達", "consecutive_below_target"),
]

_SPC_COLORS = {
    "連続上昇":   "#00A854",
    "連続降下":   "#F5222D",
    "Target超え": "#FA8C16",
    "Target未達": "#1890FF",
}


def check_spc_alerts(dry_run: bool = False) -> list[dict]:
    """SPC ルール違反 (7日以上の連続) を検出して通知する。
    Target = 前日終値 × 1.005 (前日比 +0.5%)。
    """
    codes_filter = "AND s.stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        SELECT DISTINCT ON (std.stock_code)
            std.stock_code, s.company_name_ja,
            std.trade_date, std.daily_return,
            std.spc_flag_run_up, std.spc_flag_run_down,
            std.spc_flag_above_target, std.spc_flag_below_target,
            std.consecutive_rise, std.consecutive_decline,
            std.consecutive_above_target, std.consecutive_below_target,
            s.price_latest
        FROM stock_technical_daily std
        JOIN stocks s ON s.stock_code = std.stock_code
        WHERE std.spc_flag = TRUE
          AND s.is_active = TRUE
          {codes_filter}
        ORDER BY std.stock_code, std.trade_date DESC
    """)
    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    triggered: list[dict] = []
    for r in rows:
        price        = float(r["price_latest"]) if r["price_latest"] else None
        daily_return = float(r["daily_return"]) if r["daily_return"] else None
        for flag_col, alert_type, label, count_col in _SPC_RULE_CHECKS:
            if not r[flag_col]:
                continue
            if _already_sent(r["stock_code"], alert_type, r["trade_date"]):
                continue
            triggered.append({
                "code":         r["stock_code"],
                "name":         r["company_name_ja"],
                "date":         r["trade_date"],
                "label":        label,
                "alert_type":   alert_type,
                "days":         r[count_col],
                "price":        price,
                "daily_return": daily_return,
            })

    if not triggered:
        log.info("SPC アラート: 新規アラートなし")
        return []

    def _badge(label: str) -> str:
        color = _SPC_COLORS.get(label, "#333")
        return f"<span style='color:{color};font-weight:bold'>{label}</span>"

    def _fmt_price(t: dict) -> str:
        return f"¥{t['price']:,.0f}" if t["price"] is not None else "-"

    def _fmt_ret(t: dict) -> str:
        return f"{t['daily_return'] * 100:.2f}%" if t["daily_return"] is not None else "-"

    rows_html = "".join(
        f"<tr style='background:#{'fff9f0' if t['label'] in ('Target超え','連続上昇') else 'f0f4ff'}'>"
        f"<td>{t['code']}</td><td>{t['name']}</td>"
        f"<td>{_badge(t['label'])}</td>"
        f"<td style='text-align:center'><b>{t['days']}日</b></td>"
        f"<td style='text-align:right'>{_fmt_price(t)}</td>"
        f"<td style='text-align:right'>{_fmt_ret(t)}</td>"
        f"<td>{t['date']}</td></tr>"
        for t in triggered
    )

    html = _wrap_html(
        f"SPC アラート {len(triggered)} 件",
        f"""
        <h2>SPC 管理アラート ({TODAY})</h2>
        <p>Target = 前日終値 × 1.005 (前日比 +0.5%) | Run Rule: 7日以上継続でフラグ</p>
        <table border="1" cellpadding="6" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#f5f5f5">
            <tr><th>コード</th><th>銘柄名</th><th>ルール</th><th>連続日数</th>
                <th>現在値</th><th>日次騰落率</th><th>日付</th></tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style="font-size:11px;color:#999">
          連続上昇/降下: 終値が前日より上/下が7日以上継続<br>
          Target超え/未達: 日次騰落率 ≥/&lt; +0.5% が7日以上継続
        </p>
        """,
    )

    send_email(f"【SPC アラート】{TODAY} ({len(triggered)} 件)", html, dry_run)

    if not dry_run:
        for t in triggered:
            price_str = f"¥{t['price']:,.0f}" if t["price"] is not None else "-"
            _record_sent(
                t["code"], t["alert_type"], t["date"],
                f"{t['label']} {t['days']}日 {price_str}",
            )

    return triggered


# ══════════════════════════════════════════════════════════════
# 5. 毎朝サマリーレポート
# ══════════════════════════════════════════════════════════════

def send_morning_report(dry_run: bool = False) -> None:
    """ウォッチリスト銘柄の現況サマリーをメール送信する。"""
    codes_filter = "AND s.stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        SELECT s.stock_code, s.company_name_ja,
               s.price_latest, s.price_vs_52w_high,
               s.rsi_14, s.per_ttm, s.pbr, s.dividend_yield,
               s.ma7, s.ma49, s.ma98,
               s.market_cap_jpy
        FROM stocks s
        WHERE s.is_active = TRUE
          {codes_filter}
        ORDER BY s.market_cap_jpy DESC NULLS LAST
        LIMIT 50
    """)
    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    if not rows:
        log.info("レポート: 対象銘柄なし")
        return

    def _rsi_badge(rsi: Optional[float]) -> str:
        if rsi is None:
            return "-"
        if rsi >= RSI_HIGH:
            return f"<span style='color:red'>{rsi:.1f} ⚠️</span>"
        if rsi <= RSI_LOW:
            return f"<span style='color:blue'>{rsi:.1f} ⚠️</span>"
        return f"{rsi:.1f}"

    def _cross_badge(ma7: Optional[float], ma49: Optional[float]) -> str:
        if ma7 is None or ma49 is None:
            return "-"
        if ma7 > ma49:
            return "<span style='color:#b8860b'>▲GC</span>"
        return "<span style='color:#4169e1'>▼DC</span>"

    def _fmt_cap(v: Optional[int]) -> str:
        if v is None:
            return "-"
        return f"{v/1e12:.2f}兆" if v >= 1e12 else f"{v/1e8:.0f}億"

    rows_html = "".join(
        f"<tr>"
        f"<td>{r['stock_code']}</td><td>{r['company_name_ja']}</td>"
        f"<td style='text-align:right'>¥{float(r['price_latest']):,.0f}</td>"
        f"<td style='text-align:right'>{float(r['price_vs_52w_high'])*100:.1f}%</td>"
        f"<td style='text-align:center'>{_rsi_badge(float(r['rsi_14']) if r['rsi_14'] else None)}</td>"
        f"<td style='text-align:center'>{_cross_badge(float(r['ma7']) if r['ma7'] else None, float(r['ma49']) if r['ma49'] else None)}</td>"
        f"<td style='text-align:right'>{float(r['per_ttm']):.1f}x</td>"
        f"<td style='text-align:right'>{float(r['pbr']):.2f}x</td>"
        f"<td style='text-align:right'>{float(r['dividend_yield'])*100:.2f}%</td>"
        f"<td style='text-align:right'>{_fmt_cap(r['market_cap_jpy'])}</td>"
        f"</tr>"
        for r in rows
        if r["price_latest"] and r["per_ttm"] and r["pbr"] and r["dividend_yield"]
    )

    html = _wrap_html(
        f"毎朝レポート {TODAY}",
        f"""
        <h2>ウォッチリスト サマリー ({TODAY})</h2>
        <p>対象: {len(rows)} 銘柄 |
           RSI 過熱基準: ≥{RSI_HIGH} / 売られすぎ: ≤{RSI_LOW}</p>
        <table border="1" cellpadding="5" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#f5f5f5">
            <tr>
              <th>コード</th><th>銘柄名</th><th>株価</th><th>52週比</th>
              <th>RSI(14)</th><th>MA7/49</th>
              <th>PER</th><th>PBR</th><th>配当</th><th>時価総額</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style="font-size:11px;color:#999">▲GC = MA7 > MA49 (ゴールデン) / ▼DC = MA7 < MA49 (デッド)</p>
        """,
    )

    send_email(f"【株式レポート】毎朝サマリー {TODAY}", html, dry_run)

    if not dry_run:
        _record_sent(None, "morning_report", TODAY, f"{len(rows)} stocks")


# ══════════════════════════════════════════════════════════════
# 6. 3σ 外れ値アラート
# ══════════════════════════════════════════════════════════════

def check_sigma3_alerts(dry_run: bool = False) -> list[dict]:
    """直近2日以内に3σバンドを突破した銘柄を検出して通知する。"""
    codes_filter = "AND s.stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        SELECT DISTINCT ON (std.stock_code)
            std.stock_code, s.company_name_ja, std.trade_date,
            s.price_latest,
            std.sigma3_upper_49, std.sigma3_lower_49, std.is_outlier_49, std.std_49,
            std.sigma3_upper_98, std.sigma3_lower_98, std.is_outlier_98, std.std_98
        FROM stock_technical_daily std
        JOIN stocks s ON s.stock_code = std.stock_code
        WHERE (std.is_outlier_49 = TRUE OR std.is_outlier_98 = TRUE)
          AND std.trade_date >= CURRENT_DATE - INTERVAL '2 days'
          AND s.is_active = TRUE
          {codes_filter}
        ORDER BY std.stock_code, std.trade_date DESC
    """)
    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    triggered = []
    for r in rows:
        alert_type = "sigma3_98" if r["is_outlier_98"] else "sigma3_49"
        if _already_sent(r["stock_code"], alert_type, r["trade_date"]):
            continue
        triggered.append(dict(r))

    if not triggered:
        log.info("3σ アラート: 新規アラートなし")
        return []

    def _sigma_row(r: dict) -> str:
        price = float(r["price_latest"]) if r["price_latest"] else 0
        out98 = r["is_outlier_98"]
        if out98:
            upper = float(r["sigma3_upper_98"]) if r["sigma3_upper_98"] else 0
            lower = float(r["sigma3_lower_98"]) if r["sigma3_lower_98"] else 0
            std   = float(r["std_98"]) if r["std_98"] else 1
            label, bg = "98日 ±3σ", "#fff0f0"
        else:
            upper = float(r["sigma3_upper_49"]) if r["sigma3_upper_49"] else 0
            lower = float(r["sigma3_lower_49"]) if r["sigma3_lower_49"] else 0
            std   = float(r["std_49"]) if r["std_49"] else 1
            label, bg = "49日 ±3σ", "#fff7e6"

        if price > upper:
            direction, deviation = "▲ 上抜け", (price - upper) / std
            dir_color = "#c0392b"
        else:
            direction, deviation = "▼ 下抜け", (lower - price) / std
            dir_color = "#2980b9"

        return (
            f"<tr style='background:{bg}'>"
            f"<td><b>{r['stock_code']}</b></td><td>{r['company_name_ja']}</td>"
            f"<td style='color:{dir_color};font-weight:bold'>{direction}</td>"
            f"<td style='font-weight:bold'>{'🔴' if out98 else '🟠'} {label}</td>"
            f"<td style='text-align:right;font-weight:bold'>¥{price:,.0f}</td>"
            f"<td style='text-align:right'>¥{upper:,.0f}</td>"
            f"<td style='text-align:right'>¥{lower:,.0f}</td>"
            f"<td style='text-align:right;color:{dir_color};font-weight:bold'>+{deviation:.2f}σ</td>"
            f"<td>{r['trade_date']}</td></tr>"
        )

    html = _wrap_html(
        f"3σ 外れ値アラート {len(triggered)} 件",
        f"""
        <h2 style='color:#c0392b'>⚠️ 3σ 外れ値アラート ({TODAY})</h2>
        <p>統計的外れ値 (μ ± 3σ バンド突破) を <b>{len(triggered)} 件</b>検出しました。</p>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#2c3e50;color:#fff">
            <tr><th>コード</th><th>銘柄名</th><th>方向</th><th>バンド種別</th>
                <th>現在値</th><th>上限(+3σ)</th><th>下限(-3σ)</th><th>偏差</th><th>日付</th></tr>
          </thead>
          <tbody>{"".join(_sigma_row(r) for r in triggered)}</tbody>
        </table>
        <p style="font-size:11px;color:#888;margin-top:12px">
          49日: 過去49日の SMA±3×標準偏差 / 98日: 過去98日の SMA±3×標準偏差
        </p>
        """,
    )
    send_email(f"【統計アラート】3σ外れ値 {TODAY} ({len(triggered)} 件)", html, dry_run)

    if not dry_run:
        for r in triggered:
            atype = "sigma3_98" if r["is_outlier_98"] else "sigma3_49"
            _record_sent(r["stock_code"], atype, r["trade_date"],
                         f"{'98日' if r['is_outlier_98'] else '49日'} 3σ突破")
    return triggered


# ══════════════════════════════════════════════════════════════
# 7. 52週高値/安値ブレイクアウトアラート
# ══════════════════════════════════════════════════════════════

def check_52w_breakout(dry_run: bool = False) -> list[dict]:
    """52週高値更新または安値更新した銘柄を検出して通知する。"""
    codes_filter = "AND stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        SELECT stock_code, company_name_ja, price_latest,
               price_52w_high, price_52w_low, price_vs_52w_high,
               rsi_14, per_ttm, market_cap_jpy
        FROM stocks
        WHERE is_active = TRUE
          AND price_latest IS NOT NULL
          AND (price_latest >= price_52w_high OR price_latest <= price_52w_low)
          {codes_filter}
        ORDER BY market_cap_jpy DESC NULLS LAST
    """)
    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    triggered = []
    for r in rows:
        price = float(r["price_latest"])
        high  = float(r["price_52w_high"]) if r["price_52w_high"] else None
        low   = float(r["price_52w_low"])  if r["price_52w_low"]  else None
        is_high    = bool(high and price >= high)
        alert_type = "52w_high" if is_high else "52w_low"
        if _already_sent(r["stock_code"], alert_type, TODAY):
            continue
        triggered.append({**dict(r), "is_high": is_high, "alert_type": alert_type})

    if not triggered:
        log.info("52週ブレイクアウト: 新規アラートなし")
        return []

    highs = [t for t in triggered if t["is_high"]]
    lows  = [t for t in triggered if not t["is_high"]]

    def _bk_row(t: dict) -> str:
        price     = float(t["price_latest"])
        is_high   = t["is_high"]
        ref       = float(t["price_52w_high"] if is_high else t["price_52w_low"])
        pct       = (price - ref) / ref * 100 if ref else 0
        rsi       = float(t["rsi_14"]) if t["rsi_14"] else None
        cap       = float(t["market_cap_jpy"]) if t["market_cap_jpy"] else 0
        cap_str   = f"{cap/1e12:.2f}兆" if cap >= 1e12 else f"{cap/1e8:.0f}億" if cap else "-"
        rsi_color = "#e74c3c" if rsi and rsi >= 70 else "#3498db" if rsi and rsi <= 30 else "#333"
        bg, icon, color = ("#f0fff4", "🆕↑ 52週高値更新", "#27ae60") if is_high else ("#fff0f0", "🆕↓ 52週安値更新", "#e74c3c")
        return (
            f"<tr style='background:{bg}'>"
            f"<td><b>{t['stock_code']}</b></td><td>{t['company_name_ja']}</td>"
            f"<td style='color:{color};font-weight:bold'>{icon}</td>"
            f"<td style='text-align:right;font-weight:bold'>¥{price:,.0f}</td>"
            f"<td style='text-align:right'>¥{ref:,.0f}</td>"
            f"<td style='text-align:right;color:{color}'>{pct:+.2f}%</td>"
            f"<td style='text-align:center;color:{rsi_color}'>{rsi:.1f if rsi else '-'}</td>"
            f"<td style='text-align:right'>{cap_str}</td></tr>"
        )

    html = _wrap_html(
        f"52週ブレイクアウト {len(triggered)} 件",
        f"""
        <h2>📈 52週高値/安値 ブレイクアウト ({TODAY})</h2>
        <table style="margin-bottom:16px">
          <tr>
            <td style="padding:10px 20px;background:#f0fff4;border-radius:6px;margin-right:12px">
              <span style="font-size:22px;font-weight:bold;color:#27ae60">{len(highs)}</span>
              <span style="color:#888;font-size:12px"> 件 高値更新</span>
            </td>
            <td style="padding:10px 20px;background:#fff0f0;border-radius:6px">
              <span style="font-size:22px;font-weight:bold;color:#e74c3c">{len(lows)}</span>
              <span style="color:#888;font-size:12px"> 件 安値更新</span>
            </td>
          </tr>
        </table>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#2c3e50;color:#fff">
            <tr><th>コード</th><th>銘柄名</th><th>種別</th>
                <th>現在値</th><th>52週 高値/安値</th>
                <th>乖離率</th><th>RSI(14)</th><th>時価総額</th></tr>
          </thead>
          <tbody>{"".join(_bk_row(t) for t in triggered)}</tbody>
        </table>
        <p style="font-size:11px;color:#888;margin-top:12px">
          RSI 赤=過熱(≥70) / 青=売られすぎ(≤30)
        </p>
        """,
    )
    send_email(f"【ブレイクアウト】52週高値/安値更新 {TODAY} ({len(triggered)} 件)", html, dry_run)

    if not dry_run:
        for t in triggered:
            _record_sent(t["stock_code"], t["alert_type"], TODAY,
                         f"{'52W高値' if t['is_high'] else '52W安値'} ¥{float(t['price_latest']):,.0f}")
    return triggered


# ══════════════════════════════════════════════════════════════
# 8. 出来高急増アラート
# ══════════════════════════════════════════════════════════════

def check_volume_surge(threshold: float = VOLUME_SURGE_THRESHOLD, dry_run: bool = False) -> list[dict]:
    """出来高が20日平均のthreshold倍以上の銘柄を通知する。"""
    codes_filter = "AND stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        SELECT stock_code, company_name_ja, price_latest,
               avg_volume_20d, volume_ratio, rsi_14, market_cap_jpy
        FROM stocks
        WHERE is_active = TRUE
          AND volume_ratio >= :threshold
          AND volume_ratio IS NOT NULL
          {codes_filter}
        ORDER BY volume_ratio DESC
        LIMIT 30
    """)
    params: dict = {"threshold": threshold}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    triggered = []
    for r in rows:
        if _already_sent(r["stock_code"], "volume_surge", TODAY):
            continue
        triggered.append(dict(r))

    if not triggered:
        log.info("出来高急増アラート: 新規アラートなし")
        return []

    def _vol_bar(ratio: float) -> str:
        w     = min(int(ratio / threshold * 40), 120)
        color = "#e74c3c" if ratio >= threshold * 2 else "#fa8c16" if ratio >= threshold * 1.5 else "#27ae60"
        return (
            f"<span style='display:inline-flex;align-items:center;gap:5px'>"
            f"<span style='background:{color};display:inline-block;width:{w}px;height:10px;border-radius:3px'></span>"
            f"<b style='color:{color}'>{ratio:.1f}x</b></span>"
        )

    def _vol_row(r: dict) -> str:
        ratio     = float(r["volume_ratio"]) if r["volume_ratio"] else 0
        avg_v     = int(r["avg_volume_20d"]) if r["avg_volume_20d"] else 0
        today_est = int(avg_v * ratio) if avg_v else 0
        price     = float(r["price_latest"]) if r["price_latest"] else 0
        rsi       = float(r["rsi_14"]) if r["rsi_14"] else None
        rsi_color = "#e74c3c" if rsi and rsi >= 70 else "#3498db" if rsi and rsi <= 30 else "#333"
        bg        = "#fff1f0" if ratio >= threshold * 2 else "#fff7e6" if ratio >= threshold * 1.5 else "#fff"
        return (
            f"<tr style='background:{bg}'>"
            f"<td><b>{r['stock_code']}</b></td><td>{r['company_name_ja']}</td>"
            f"<td style='text-align:right'>¥{price:,.0f}</td>"
            f"<td>{_vol_bar(ratio)}</td>"
            f"<td style='text-align:right'>{today_est:,}</td>"
            f"<td style='text-align:right'>{avg_v:,}</td>"
            f"<td style='text-align:center;color:{rsi_color}'>{rsi:.1f if rsi else '-'}</td>"
            f"</tr>"
        )

    html = _wrap_html(
        f"出来高急増アラート {len(triggered)} 件",
        f"""
        <h2>📊 出来高急増アラート ({TODAY})</h2>
        <p>20日平均出来高の <b>{threshold:.0f}倍以上</b> を記録した銘柄:
           <b style="color:#e74c3c">{len(triggered)} 件</b></p>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#2c3e50;color:#fff">
            <tr><th>コード</th><th>銘柄名</th><th>株価</th>
                <th>出来高比率</th><th>推定当日出来高</th>
                <th>20日平均出来高</th><th>RSI(14)</th></tr>
          </thead>
          <tbody>{"".join(_vol_row(r) for r in triggered)}</tbody>
        </table>
        <p style="font-size:11px;color:#888;margin-top:12px">
          🔴≥{threshold*2:.0f}x  🟠≥{threshold*1.5:.0f}x  🟢≥{threshold:.0f}x — 異常な取引急増は重要シグナルです。
        </p>
        """,
    )
    send_email(f"【出来高急増】{TODAY} ({len(triggered)} 件 / ≥{threshold:.0f}x)", html, dry_run)

    if not dry_run:
        for r in triggered:
            _record_sent(r["stock_code"], "volume_surge", TODAY,
                         f"出来高比率 {float(r['volume_ratio']):.1f}x")
    return triggered


# ══════════════════════════════════════════════════════════════
# 9. 週次パフォーマンスレポート
# ══════════════════════════════════════════════════════════════

def send_weekly_report(dry_run: bool = False) -> None:
    """ウォッチリスト銘柄の週次 (5営業日) パフォーマンスレポートを送信する。"""
    codes_filter = "AND s.stock_code = ANY(:codes)" if WATCHLIST else ""
    sql = text(f"""
        WITH latest AS (
            SELECT DISTINCT ON (stock_code) stock_code, close, trade_date
            FROM stock_daily_prices ORDER BY stock_code, trade_date DESC
        ),
        prev5 AS (
            SELECT DISTINCT ON (stock_code) stock_code, close
            FROM stock_daily_prices
            WHERE trade_date <= CURRENT_DATE - INTERVAL '5 days'
            ORDER BY stock_code, trade_date DESC
        ),
        latest_tech AS (
            SELECT DISTINCT ON (stock_code)
                stock_code, spc_flag, spc_flag_run_up, spc_flag_run_down
            FROM stock_technical_daily
            ORDER BY stock_code, trade_date DESC
        )
        SELECT
            s.stock_code, s.company_name_ja,
            l.close      AS latest_close,
            l.trade_date AS latest_date,
            p.close      AS prev_close,
            (l.close - p.close) / NULLIF(p.close, 0) AS weekly_return,
            s.rsi_14, s.market_cap_jpy,
            lt.spc_flag, lt.spc_flag_run_up, lt.spc_flag_run_down
        FROM stocks s
        JOIN   latest l  ON l.stock_code = s.stock_code
        LEFT JOIN prev5 p  ON p.stock_code = s.stock_code
        LEFT JOIN latest_tech lt ON lt.stock_code = s.stock_code
        WHERE s.is_active = TRUE
          {codes_filter}
        ORDER BY weekly_return DESC NULLS LAST
    """)
    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().fetchall()

    if not rows:
        log.info("週次レポート: 対象銘柄なし")
        return

    valid      = [r for r in rows if r["weekly_return"] is not None]
    gainers10  = valid[:10]
    losers10   = list(reversed(valid[-10:]))
    avg_ret    = sum(float(r["weekly_return"]) for r in valid) / len(valid) if valid else 0
    pos_count  = sum(1 for r in valid if float(r["weekly_return"]) >= 0)
    neg_count  = len(valid) - pos_count
    spc_count  = sum(1 for r in valid if r["spc_flag"])

    def _ret_cell(ret: float) -> str:
        w      = min(int(abs(ret) * 600), 80)
        color  = "#27ae60" if ret >= 0 else "#e74c3c"
        sign   = "+" if ret >= 0 else ""
        return (
            f"<span style='display:inline-flex;align-items:center;gap:5px'>"
            f"<span style='background:{color};display:inline-block;"
            f"width:{w}px;height:9px;border-radius:2px'></span>"
            f"<b style='color:{color}'>{sign}{ret*100:.2f}%</b></span>"
        )

    def _rank_row(r: dict, rank: int) -> str:
        ret    = float(r["weekly_return"])
        price  = float(r["latest_close"]) if r["latest_close"] else 0
        rsi    = float(r["rsi_14"]) if r["rsi_14"] else None
        flags  = (" ⚡↑" if r.get("spc_flag_run_up") else " ⚡↓" if r.get("spc_flag_run_down") else " ⚡" if r.get("spc_flag") else "")
        rc     = "#e74c3c" if rsi and rsi >= 70 else "#3498db" if rsi and rsi <= 30 else "#555"
        return (
            f"<tr>"
            f"<td style='text-align:center;color:#aaa;font-size:12px'>{rank}</td>"
            f"<td><b>{r['stock_code']}</b></td><td>{r['company_name_ja']}</td>"
            f"<td style='text-align:right'>¥{price:,.0f}</td>"
            f"<td>{_ret_cell(ret)}</td>"
            f"<td style='text-align:center;color:{rc}'>{f'{rsi:.1f}' if rsi else '-'}</td>"
            f"<td style='font-size:11px;color:#888'>{flags.strip()}</td></tr>"
        )

    common_head = (
        "<thead style='background:{bg};color:#fff'>"
        "<tr><th>#</th><th>コード</th><th>銘柄名</th>"
        "<th>終値</th><th>週次騰落率</th><th>RSI</th><th>フラグ</th></tr></thead>"
    )

    html = _wrap_html(
        "週次パフォーマンスレポート",
        f"""
        <h2>📅 週次パフォーマンスレポート ({TODAY})</h2>

        <!-- KPI カード -->
        <table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:20px">
          <tr>
            <td style="text-align:center;padding:14px;background:{'#f0fff4' if avg_ret>=0 else '#fff0f0'};border-radius:8px;border:1px solid #eee">
              <div style="font-size:24px;font-weight:bold;color:{'#27ae60' if avg_ret>=0 else '#e74c3c'}">
                {'+' if avg_ret>=0 else ''}{avg_ret*100:.2f}%</div>
              <div style="font-size:11px;color:#888">平均週次リターン</div>
            </td>
            <td style="text-align:center;padding:14px;background:#f0f9f4;border-radius:8px;border:1px solid #eee">
              <div style="font-size:24px;font-weight:bold;color:#27ae60">{pos_count}</div>
              <div style="font-size:11px;color:#888">上昇銘柄数</div>
            </td>
            <td style="text-align:center;padding:14px;background:#fff0f0;border-radius:8px;border:1px solid #eee">
              <div style="font-size:24px;font-weight:bold;color:#e74c3c">{neg_count}</div>
              <div style="font-size:11px;color:#888">下落銘柄数</div>
            </td>
            <td style="text-align:center;padding:14px;background:#f9f0ff;border-radius:8px;border:1px solid #eee">
              <div style="font-size:24px;font-weight:bold;color:#722ed1">{spc_count}</div>
              <div style="font-size:11px;color:#888">SPC フラグ銘柄</div>
            </td>
          </tr>
        </table>

        <!-- 上昇ランキング -->
        <h3 style="color:#27ae60;border-left:4px solid #27ae60;padding-left:8px">
          ▲ 週間上昇 TOP10</h3>
        <table border="1" cellpadding="5" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px">
          <thead style="background:#27ae60;color:#fff">
            <tr><th>#</th><th>コード</th><th>銘柄名</th>
                <th>終値</th><th>週次騰落率</th><th>RSI</th><th>フラグ</th></tr>
          </thead>
          <tbody>{"".join(_rank_row(r, i+1) for i, r in enumerate(gainers10))}</tbody>
        </table>

        <!-- 下落ランキング -->
        <h3 style="color:#e74c3c;border-left:4px solid #e74c3c;padding-left:8px">
          ▼ 週間下落 TOP10</h3>
        <table border="1" cellpadding="5" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#e74c3c;color:#fff">
            <tr><th>#</th><th>コード</th><th>銘柄名</th>
                <th>終値</th><th>週次騰落率</th><th>RSI</th><th>フラグ</th></tr>
          </thead>
          <tbody>{"".join(_rank_row(r, i+1) for i, r in enumerate(losers10))}</tbody>
        </table>
        <p style="font-size:11px;color:#888">
          ⚡↑ SPC連続上昇フラグ / ⚡↓ SPC連続降下フラグ / ⚡ SPCその他フラグ
        </p>
        """,
    )
    send_email(f"【週次レポート】週間パフォーマンス {TODAY}", html, dry_run)
    if not dry_run:
        _record_sent(None, "weekly_report", TODAY,
                     f"{len(valid)} stocks avg={avg_ret*100:.2f}%")


# ══════════════════════════════════════════════════════════════
# 10. 配当アラート
# ══════════════════════════════════════════════════════════════

def check_dividend_alerts(days_ahead: int = DIVIDEND_ALERT_DAYS, dry_run: bool = False) -> list[dict]:
    """配当落ち日が近い銘柄と高配当スクリーニング結果を通知する。"""
    codes_filter = "AND stock_code = ANY(:codes)" if WATCHLIST else ""

    upcoming_sql = text(f"""
        SELECT stock_code, company_name_ja, price_latest,
               dividend_yield, dividend_per_share, last_ex_dividend_date,
               payout_ratio, consecutive_div_years, per_ttm
        FROM stocks
        WHERE is_active = TRUE
          AND last_ex_dividend_date BETWEEN CURRENT_DATE
              AND CURRENT_DATE + :days_ahead * INTERVAL '1 day'
          AND dividend_yield IS NOT NULL
          {codes_filter}
        ORDER BY last_ex_dividend_date ASC
    """)

    high_yield_sql = text(f"""
        SELECT stock_code, company_name_ja, price_latest,
               dividend_yield, dividend_per_share, last_ex_dividend_date,
               payout_ratio, consecutive_div_years, per_ttm
        FROM stocks
        WHERE is_active = TRUE
          AND dividend_yield >= 0.03
          AND price_latest IS NOT NULL
          {codes_filter}
        ORDER BY dividend_yield DESC
        LIMIT 15
    """)

    params: dict = {"days_ahead": days_ahead}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        upcoming   = conn.execute(upcoming_sql, params).mappings().fetchall()
        high_yield = conn.execute(high_yield_sql, params).mappings().fetchall()

    triggered = []
    for r in upcoming:
        if r["last_ex_dividend_date"] and _already_sent(
            r["stock_code"], "ex_dividend", r["last_ex_dividend_date"]
        ):
            continue
        triggered.append(dict(r))

    if not triggered and not high_yield:
        log.info("配当アラート: 対象なし")
        return []

    def _div_row(r: dict, highlight: bool = False) -> str:
        price  = float(r["price_latest"]) if r["price_latest"] else 0
        dy     = float(r["dividend_yield"]) * 100 if r["dividend_yield"] else 0
        dps    = float(r["dividend_per_share"]) if r["dividend_per_share"] else 0
        pr     = float(r["payout_ratio"]) * 100 if r["payout_ratio"] else None
        cons   = int(r["consecutive_div_years"]) if r["consecutive_div_years"] else 0
        ex_dt  = r["last_ex_dividend_date"] or "-"
        per    = float(r["per_ttm"]) if r["per_ttm"] else None
        dy_color = "#e74c3c" if dy >= 5 else "#fa8c16" if dy >= 3.5 else "#27ae60"
        # 連続配当年数バッジ
        stars  = "🏆" if cons >= 30 else "⭐⭐" if cons >= 15 else "⭐" if cons >= 5 else ""
        bg     = "#f6ffed" if highlight else "#fff"
        return (
            f"<tr style='background:{bg}'>"
            f"<td><b>{r['stock_code']}</b></td><td>{r['company_name_ja']}</td>"
            f"<td style='text-align:right'>¥{price:,.0f}</td>"
            f"<td style='text-align:right;color:{dy_color};font-weight:bold'>{dy:.2f}%</td>"
            f"<td style='text-align:right'>¥{dps:.1f}</td>"
            f"<td style='text-align:right'>{'%.1f%%' % pr if pr else '-'}</td>"
            f"<td style='text-align:right'>{'%.1f' % per if per else '-'}x</td>"
            f"<td style='text-align:center'>{stars} {cons}年</td>"
            f"<td style='text-align:center;font-weight:bold'>{ex_dt}</td></tr>"
        )

    thead = (
        "<thead style='background:#2c3e50;color:#fff'>"
        "<tr><th>コード</th><th>銘柄名</th><th>株価</th><th>配当利回り</th>"
        "<th>1株配当</th><th>配当性向</th><th>PER</th><th>連続配当</th><th>配当落ち日</th></tr></thead>"
    )

    upcoming_html = (
        "".join(_div_row(r, True) for r in triggered)
        if triggered
        else f"<tr><td colspan='9' style='text-align:center;color:#888;padding:12px'>"
             f"直近 {days_ahead} 日以内の配当落ち日なし</td></tr>"
    )

    html = _wrap_html(
        f"配当アラート {TODAY}",
        f"""
        <h2>💰 配当アラート ({TODAY})</h2>

        <h3 style="color:#fa8c16;border-left:4px solid #fa8c16;padding-left:8px">
          📅 直近 {days_ahead} 日以内に配当落ち日が到来する銘柄
          <span style="font-size:14px;font-weight:normal">({len(triggered)} 件)</span>
        </h3>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:24px">
          {thead}<tbody>{upcoming_html}</tbody>
        </table>

        <h3 style="color:#27ae60;border-left:4px solid #27ae60;padding-left:8px">
          💎 高配当スクリーニング (配当利回り ≥ 3%)
          <span style="font-size:14px;font-weight:normal">({len(high_yield)} 件)</span>
        </h3>
        <table border="1" cellpadding="7" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px">
          {thead}<tbody>{"".join(_div_row(dict(r)) for r in high_yield)}</tbody>
        </table>
        <p style="font-size:11px;color:#888;margin-top:12px">
          🏆 連続30年以上 / ⭐⭐ 15年以上 / ⭐ 5年以上 | 配当性向が高すぎる場合は減配リスクに注意
        </p>
        """,
    )
    send_email(f"【配当アラート】{TODAY} (落ち日 {len(triggered)} 件)", html, dry_run)

    if not dry_run:
        for r in triggered:
            _record_sent(
                r["stock_code"], "ex_dividend", r["last_ex_dividend_date"],
                f"配当落ち日 {r['last_ex_dividend_date']} 利回り {float(r['dividend_yield'])*100:.2f}%",
            )
    return triggered


# ══════════════════════════════════════════════════════════════
# 11. 業種別サマリーレポート
# ══════════════════════════════════════════════════════════════

def send_sector_report(dry_run: bool = False) -> None:
    """東証33業種別の集計サマリーを送信する。"""
    sql = text("""
        WITH tech AS (
            SELECT DISTINCT ON (stock_code) stock_code, spc_flag
            FROM stock_technical_daily
            ORDER BY stock_code, trade_date DESC
        )
        SELECT
            im.industry_name_ja,
            COUNT(s.stock_code)                             AS stock_count,
            AVG(s.per_ttm)                                  AS avg_per,
            AVG(s.pbr)                                      AS avg_pbr,
            AVG(s.roe)                                      AS avg_roe,
            AVG(s.dividend_yield)                           AS avg_div,
            AVG(s.operating_margin)                         AS avg_op_margin,
            AVG(s.rsi_14)                                   AS avg_rsi,
            SUM(s.market_cap_jpy)                           AS total_cap,
            COUNT(CASE WHEN t.spc_flag THEN 1 END)          AS spc_count,
            AVG(s.price_vs_52w_high)                        AS avg_52w_pct
        FROM stocks s
        JOIN industry_master im ON s.industry_code = im.industry_code
        LEFT JOIN tech t ON t.stock_code = s.stock_code
        WHERE s.is_active = TRUE
        GROUP BY im.industry_code, im.industry_name_ja
        ORDER BY total_cap DESC NULLS LAST
    """)

    with engine.connect() as conn:
        rows = conn.execute(sql).mappings().fetchall()

    if not rows:
        log.info("業種レポート: 対象データなし")
        return

    def _cap(v) -> str:
        if v is None:
            return "-"
        v = float(v)
        return f"{v/1e12:.1f}兆" if v >= 1e12 else f"{v/1e8:.0f}億"

    def _rsi_td(v) -> str:
        if v is None:
            return "<td style='text-align:center'>-</td>"
        v = float(v)
        c = "#e74c3c" if v >= 70 else "#3498db" if v <= 30 else "#27ae60"
        return f"<td style='text-align:center;color:{c};font-weight:bold'>{v:.1f}</td>"

    def _pct_td(v) -> str:
        if v is None:
            return "<td>-</td>"
        return f"<td style='text-align:right'>{float(v)*100:.2f}%</td>"

    total_cap = sum(float(r["total_cap"]) for r in rows if r["total_cap"])

    sector_rows = ""
    for r in rows:
        cap       = float(r["total_cap"]) if r["total_cap"] else 0
        cap_share = cap / total_cap * 100 if total_cap else 0
        spc       = int(r["spc_count"]) if r["spc_count"] else 0
        spc_badge = (
            f"<span style='color:#e74c3c;font-weight:bold'>{spc}</span>"
            if spc > 0 else "-"
        )
        per = float(r["avg_per"]) if r["avg_per"] else None
        pbr = float(r["avg_pbr"]) if r["avg_pbr"] else None
        w52  = float(r["avg_52w_pct"]) if r["avg_52w_pct"] else None
        w52_color = "#27ae60" if w52 and w52 >= 0.95 else "#e74c3c" if w52 and w52 < 0.80 else "#333"

        sector_rows += (
            f"<tr>"
            f"<td><b>{r['industry_name_ja']}</b></td>"
            f"<td style='text-align:right'>{r['stock_count']}</td>"
            f"<td style='text-align:right'>{'%.1f' % per if per else '-'}x</td>"
            f"<td style='text-align:right'>{'%.2f' % pbr if pbr else '-'}x</td>"
            f"{_pct_td(r['avg_roe'])}{_pct_td(r['avg_div'])}{_pct_td(r['avg_op_margin'])}"
            f"{_rsi_td(r['avg_rsi'])}"
            f"<td style='text-align:right'>{_cap(r['total_cap'])}</td>"
            f"<td style='text-align:right'>"
            f"<span style='display:inline-block;background:#4169e1;width:{int(cap_share*3)}px;"
            f"height:9px;border-radius:2px'></span> {cap_share:.1f}%</td>"
            f"<td style='text-align:center;color:{'#e74c3c' if w52 and w52 >= 0.98 else w52_color}'>"
            f"{'%.1f%%' % (w52*100) if w52 else '-'}</td>"
            f"<td style='text-align:center'>{spc_badge}</td>"
            f"</tr>"
        )

    html = _wrap_html(
        "業種別サマリーレポート",
        f"""
        <h2>🏭 業種別サマリーレポート ({TODAY})</h2>
        <p>東証33業種 | {len(rows)} 業種 / {sum(r['stock_count'] for r in rows)} 銘柄</p>
        <table border="1" cellpadding="6" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:12px">
          <thead style="background:#2c3e50;color:#fff">
            <tr>
              <th>業種</th><th>銘柄数</th><th>平均PER</th><th>平均PBR</th>
              <th>平均ROE</th><th>平均配当利回り</th><th>平均営業利益率</th>
              <th>平均RSI</th><th>時価総額合計</th><th>シェア</th>
              <th>52週高値比</th><th>SPC⚠</th>
            </tr>
          </thead>
          <tbody>{sector_rows}</tbody>
        </table>
        <p style="font-size:11px;color:#888;margin-top:12px">
          RSI 赤=過熱(≥70) / 青=売られすぎ(≤30) / 緑=通常
          | SPC⚠ = SPC フラグ立ち銘柄数 | シェア = 時価総額の全体占有率
        </p>
        """,
    )
    send_email(f"【業種レポート】業種別サマリー {TODAY}", html, dry_run)
    if not dry_run:
        _record_sent(None, "sector_report", TODAY, f"{len(rows)} industries")


# ══════════════════════════════════════════════════════════════
# 12. 月次ポートフォリオレポート
# ══════════════════════════════════════════════════════════════

def send_monthly_report(dry_run: bool = False) -> None:
    """月次の詳細パフォーマンス・バリュエーション分析レポートを送信する。"""
    codes_filter = "AND s.stock_code = ANY(:codes)" if WATCHLIST else ""

    # 月次騰落率
    perf_sql = text(f"""
        WITH month_start AS (
            SELECT DISTINCT ON (stock_code) stock_code, close
            FROM stock_daily_prices
            WHERE trade_date >= date_trunc('month', CURRENT_DATE)
            ORDER BY stock_code, trade_date ASC
        ),
        month_end AS (
            SELECT DISTINCT ON (stock_code) stock_code, close
            FROM stock_daily_prices
            ORDER BY stock_code, trade_date DESC
        ),
        latest_tech AS (
            SELECT DISTINCT ON (stock_code)
                stock_code, spc_flag, spc_flag_run_up, spc_flag_run_down,
                is_outlier_49, is_outlier_98
            FROM stock_technical_daily
            ORDER BY stock_code, trade_date DESC
        )
        SELECT
            s.stock_code, s.company_name_ja,
            e.close AS latest_close, b.close AS month_start_close,
            (e.close - b.close) / NULLIF(b.close, 0) AS monthly_return,
            s.per_ttm, s.pbr, s.dividend_yield, s.rsi_14, s.market_cap_jpy,
            lt.spc_flag, lt.spc_flag_run_up, lt.spc_flag_run_down,
            lt.is_outlier_49, lt.is_outlier_98
        FROM stocks s
        JOIN month_end   e  ON e.stock_code = s.stock_code
        LEFT JOIN month_start b  ON b.stock_code = s.stock_code
        LEFT JOIN latest_tech lt ON lt.stock_code = s.stock_code
        WHERE s.is_active = TRUE
          {codes_filter}
        ORDER BY monthly_return DESC NULLS LAST
    """)

    # RSI 分布
    rsi_sql = text("""
        SELECT
            CASE
                WHEN rsi_14 >= 70 THEN '🔴 過熱 (≥70)'
                WHEN rsi_14 >= 50 THEN '🟠 強気 (50-70)'
                WHEN rsi_14 >= 30 THEN '🟢 中立 (30-50)'
                ELSE               '🔵 売られすぎ (<30)'
            END AS zone,
            COUNT(*) AS cnt
        FROM stocks
        WHERE is_active = TRUE AND rsi_14 IS NOT NULL
        GROUP BY zone ORDER BY MIN(rsi_14) DESC
    """)

    # バリュエーション中央値
    val_sql = text("""
        SELECT
            AVG(per_ttm)        AS avg_per,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY per_ttm) AS med_per,
            AVG(pbr)            AS avg_pbr,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pbr)     AS med_pbr,
            AVG(roe)            AS avg_roe,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roe)      AS med_roe,
            AVG(dividend_yield) AS avg_div,
            COUNT(*) FILTER (WHERE per_ttm < 15 AND pbr < 1) AS deep_value_count,
            COUNT(*)            AS total
        FROM stocks
        WHERE is_active = TRUE AND per_ttm IS NOT NULL AND per_ttm > 0
    """)

    params: dict = {}
    if WATCHLIST:
        params["codes"] = WATCHLIST

    with engine.connect() as conn:
        perf_rows = conn.execute(perf_sql, params).mappings().fetchall()
        rsi_dist  = conn.execute(rsi_sql).mappings().fetchall()
        vs        = conn.execute(val_sql).mappings().fetchone()

    if not perf_rows or not vs:
        log.info("月次レポート: 対象データなし")
        return

    valid     = [r for r in perf_rows if r["monthly_return"] is not None]
    gainers10 = valid[:10]
    losers10  = list(reversed(valid[-10:]))
    avg_ret   = sum(float(r["monthly_return"]) for r in valid) / len(valid) if valid else 0
    pos_count = sum(1 for r in valid if float(r["monthly_return"]) >= 0)
    neg_count = len(valid) - pos_count
    spc_count = sum(1 for r in valid if r["spc_flag"])
    out_count = sum(1 for r in valid if r["is_outlier_98"])

    month_str = TODAY.strftime("%Y年%m月") if hasattr(TODAY, "strftime") else str(TODAY)[:7]

    def _perf_row(r: dict, rank: int) -> str:
        ret   = float(r["monthly_return"])
        price = float(r["latest_close"]) if r["latest_close"] else 0
        rsi   = float(r["rsi_14"]) if r["rsi_14"] else None
        color = "#27ae60" if ret >= 0 else "#e74c3c"
        w     = min(int(abs(ret) * 400), 80)
        flags = []
        if r.get("spc_flag_run_up"):   flags.append("⚡↑")
        elif r.get("spc_flag_run_down"): flags.append("⚡↓")
        elif r.get("spc_flag"):         flags.append("⚡")
        if r.get("is_outlier_98"):      flags.append("⚠98σ")
        elif r.get("is_outlier_49"):    flags.append("⚠49σ")
        rc = "#e74c3c" if rsi and rsi >= 70 else "#3498db" if rsi and rsi <= 30 else "#555"
        return (
            f"<tr>"
            f"<td style='text-align:center;color:#aaa'>{rank}</td>"
            f"<td><b>{r['stock_code']}</b></td><td>{r['company_name_ja']}</td>"
            f"<td style='text-align:right'>¥{price:,.0f}</td>"
            f"<td><span style='background:{color};display:inline-block;"
            f"width:{w}px;height:8px;border-radius:2px;vertical-align:middle'></span>"
            f" <b style='color:{color}'>{'+' if ret>=0 else ''}{ret*100:.2f}%</b></td>"
            f"<td style='text-align:center;color:{rc}'>{f'{rsi:.1f}' if rsi else '-'}</td>"
            f"<td style='font-size:11px;color:#888'>{' '.join(flags)}</td></tr>"
        )

    # RSI 分布バー
    total_rsi  = sum(r["cnt"] for r in rsi_dist)
    zone_colors = {"🔴 過熱": "#e74c3c", "🟠 強気": "#fa8c16", "🟢 中立": "#27ae60", "🔵 売られすぎ": "#3498db"}
    rsi_rows   = ""
    for r in rsi_dist:
        pct   = r["cnt"] / total_rsi * 100 if total_rsi else 0
        color = next((v for k, v in zone_colors.items() if k in r["zone"]), "#888")
        rsi_rows += (
            f"<tr>"
            f"<td style='color:{color};font-weight:bold;white-space:nowrap'>{r['zone']}</td>"
            f"<td style='text-align:right;width:50px'>{r['cnt']}</td>"
            f"<td style='padding-left:8px'>"
            f"<div style='background:{color};width:{int(pct*3)}px;height:14px;border-radius:3px'></div></td>"
            f"<td style='text-align:right;color:{color};font-weight:bold'>{pct:.1f}%</td></tr>"
        )

    def _vfmt(v, fmt=".2f") -> str:
        return f"{float(v):{fmt}}" if v is not None else "-"

    html = _wrap_html(
        f"{month_str} 月次ポートフォリオレポート",
        f"""
        <h2>📊 {month_str} 月次ポートフォリオレポート ({TODAY})</h2>

        <!-- 月次 KPI -->
        <table style="width:100%;border-collapse:separate;border-spacing:8px;margin-bottom:24px">
          <tr>
            <td style="text-align:center;padding:16px;background:{'#f0fff4' if avg_ret>=0 else '#fff0f0'};border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:{'#27ae60' if avg_ret>=0 else '#e74c3c'}">
                {'+' if avg_ret>=0 else ''}{avg_ret*100:.2f}%</div>
              <div style="font-size:11px;color:#888;margin-top:4px">月次平均騰落率</div>
            </td>
            <td style="text-align:center;padding:16px;background:#f0f9f4;border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:#27ae60">{pos_count}</div>
              <div style="font-size:11px;color:#888;margin-top:4px">上昇銘柄</div>
            </td>
            <td style="text-align:center;padding:16px;background:#fff0f0;border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:#e74c3c">{neg_count}</div>
              <div style="font-size:11px;color:#888;margin-top:4px">下落銘柄</div>
            </td>
            <td style="text-align:center;padding:16px;background:#f9f0ff;border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:#722ed1">{spc_count}</div>
              <div style="font-size:11px;color:#888;margin-top:4px">SPC フラグ</div>
            </td>
            <td style="text-align:center;padding:16px;background:#fff7e6;border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:#fa8c16">{out_count}</div>
              <div style="font-size:11px;color:#888;margin-top:4px">3σ 外れ値(98日)</div>
            </td>
            <td style="text-align:center;padding:16px;background:#f0f4ff;border-radius:8px;border:1px solid #ddd">
              <div style="font-size:26px;font-weight:bold;color:#4169e1">{_vfmt(vs['avg_per'], '.1f')}x</div>
              <div style="font-size:11px;color:#888;margin-top:4px">平均PER</div>
            </td>
          </tr>
        </table>

        <!-- 月間上昇 TOP10 -->
        <h3 style="color:#27ae60;border-left:4px solid #27ae60;padding-left:8px">▲ 月間上昇 TOP10</h3>
        <table border="1" cellpadding="5" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:20px">
          <thead style="background:#27ae60;color:#fff">
            <tr><th>#</th><th>コード</th><th>銘柄名</th><th>株価</th><th>月次騰落率</th><th>RSI</th><th>フラグ</th></tr>
          </thead>
          <tbody>{"".join(_perf_row(r, i+1) for i, r in enumerate(gainers10))}</tbody>
        </table>

        <!-- 月間下落 TOP10 -->
        <h3 style="color:#e74c3c;border-left:4px solid #e74c3c;padding-left:8px">▼ 月間下落 TOP10</h3>
        <table border="1" cellpadding="5" cellspacing="0"
               style="border-collapse:collapse;width:100%;font-size:13px;margin-bottom:24px">
          <thead style="background:#e74c3c;color:#fff">
            <tr><th>#</th><th>コード</th><th>銘柄名</th><th>株価</th><th>月次騰落率</th><th>RSI</th><th>フラグ</th></tr>
          </thead>
          <tbody>{"".join(_perf_row(r, i+1) for i, r in enumerate(losers10))}</tbody>
        </table>

        <!-- RSI 分布 -->
        <table style="width:100%;margin-bottom:24px">
          <tr>
            <td style="vertical-align:top;width:48%">
              <h3 style="border-left:4px solid #4169e1;padding-left:8px">📈 RSI 分布</h3>
              <table cellpadding="5" cellspacing="0" style="width:100%;font-size:13px">
                <tbody>{rsi_rows}</tbody>
              </table>
            </td>
            <td style="width:4%"></td>
            <td style="vertical-align:top;width:48%">
              <h3 style="border-left:4px solid #fa8c16;padding-left:8px">💡 バリュエーション (全銘柄)</h3>
              <table border="1" cellpadding="6" cellspacing="0"
                     style="border-collapse:collapse;width:100%;font-size:13px">
                <thead style="background:#f5f5f5">
                  <tr><th>指標</th><th>平均</th><th>中央値</th></tr>
                </thead>
                <tbody>
                  <tr><td>PER</td>
                      <td style="text-align:right">{_vfmt(vs['avg_per'], '.2f')}x</td>
                      <td style="text-align:right">{_vfmt(vs['med_per'], '.2f')}x</td></tr>
                  <tr><td>PBR</td>
                      <td style="text-align:right">{_vfmt(vs['avg_pbr'], '.2f')}x</td>
                      <td style="text-align:right">{_vfmt(vs['med_pbr'], '.2f')}x</td></tr>
                  <tr><td>ROE</td>
                      <td style="text-align:right">{f"{float(vs['avg_roe'])*100:.2f}%" if vs['avg_roe'] else '-'}</td>
                      <td style="text-align:right">{f"{float(vs['med_roe'])*100:.2f}%" if vs['med_roe'] else '-'}</td></tr>
                  <tr><td>配当利回り</td>
                      <td style="text-align:right">{f"{float(vs['avg_div'])*100:.2f}%" if vs['avg_div'] else '-'}</td>
                      <td style="text-align:right">-</td></tr>
                  <tr><td>割安 (PER&lt;15 &amp; PBR&lt;1)</td>
                      <td colspan="2" style="text-align:center;font-weight:bold;color:#27ae60">
                        {vs['deep_value_count']} 銘柄</td></tr>
                </tbody>
              </table>
            </td>
          </tr>
        </table>
        <p style="font-size:11px;color:#888">
          ⚡↑ SPC連続上昇 / ⚡↓ SPC連続降下 / ⚡ SPCその他 / ⚠σ = 3σ外れ値
        </p>
        """,
    )
    send_email(f"【月次レポート】{month_str} ポートフォリオ分析", html, dry_run)
    if not dry_run:
        _record_sent(None, "monthly_report", TODAY,
                     f"avg={avg_ret*100:.2f}% {len(valid)} stocks")


# ══════════════════════════════════════════════════════════════
# ユーティリティ
# ══════════════════════════════════════════════════════════════

def _get_name(code: str, conn) -> str:
    row = conn.execute(
        text("SELECT company_name_ja FROM stocks WHERE stock_code = :c"), {"c": code}
    ).fetchone()
    return row[0] if row else code


def _wrap_html(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: 'Meiryo', 'Hiragino Sans', sans-serif; font-size:14px; color:#333; padding:20px; }}
  table {{ border-color:#ddd; }}
  th {{ background:#f5f5f5; }}
  h2 {{ color:#1a1a2e; border-left:4px solid #4169e1; padding-left:8px; }}
</style>
</head><body>
{body}
<hr style="margin-top:32px">
<p style="font-size:11px;color:#aaa">
  生成: {TODAY} | 株式分析システム (自動送信)
</p>
</body></html>"""


# ══════════════════════════════════════════════════════════════
# エントリーポイント
# ══════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="株式アラート通知 (Outlook SMTP)")
    parser.add_argument(
        "--mode",
        choices=[
            "all", "cross", "price", "rsi", "spc", "report",
            "sigma3", "breakout", "volume", "weekly", "dividend", "sector", "monthly",
        ],
        default="all",
        help="実行するアラート種別 (デフォルト: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="メール送信せずにログ出力のみ行う",
    )
    parser.add_argument(
        "--volume-threshold",
        type=float,
        default=VOLUME_SURGE_THRESHOLD,
        metavar="X",
        help=f"出来高急増アラートの倍率閾値 (デフォルト: {VOLUME_SURGE_THRESHOLD})",
    )
    parser.add_argument(
        "--dividend-days",
        type=int,
        default=DIVIDEND_ALERT_DAYS,
        metavar="N",
        help=f"配当落ち日アラートの先読み日数 (デフォルト: {DIVIDEND_ALERT_DAYS})",
    )
    args = parser.parse_args()

    log.info(f"モード: {args.mode} / dry-run: {args.dry_run} / 送信先: {NOTIFY_TO}")

    if args.mode in ("all", "cross"):
        found = check_crosses(dry_run=args.dry_run)
        log.info(f"クロスアラート: {len(found)} 件")

    if args.mode in ("all", "price"):
        found = check_price_alerts(dry_run=args.dry_run)
        log.info(f"価格アラート: {len(found)} 件")

    if args.mode in ("all", "rsi"):
        found = check_rsi_alerts(dry_run=args.dry_run)
        log.info(f"RSI アラート: {len(found)} 件")

    if args.mode in ("all", "spc"):
        found = check_spc_alerts(dry_run=args.dry_run)
        log.info(f"SPC アラート: {len(found)} 件")

    if args.mode in ("all", "report"):
        send_morning_report(dry_run=args.dry_run)
        log.info("毎朝レポート: 送信完了")

    if args.mode in ("all", "sigma3"):
        found = check_sigma3_alerts(dry_run=args.dry_run)
        log.info(f"3σ アラート: {len(found)} 件")

    if args.mode in ("all", "breakout"):
        found = check_52w_breakout(dry_run=args.dry_run)
        log.info(f"52週ブレイクアウト: {len(found)} 件")

    if args.mode in ("all", "volume"):
        found = check_volume_surge(threshold=args.volume_threshold, dry_run=args.dry_run)
        log.info(f"出来高急増アラート: {len(found)} 件")

    if args.mode in ("weekly",):
        send_weekly_report(dry_run=args.dry_run)
        log.info("週次レポート: 送信完了")

    if args.mode in ("dividend",):
        found = check_dividend_alerts(days_ahead=args.dividend_days, dry_run=args.dry_run)
        log.info(f"配当アラート: {len(found)} 件")

    if args.mode in ("sector",):
        send_sector_report(dry_run=args.dry_run)
        log.info("業種レポート: 送信完了")

    if args.mode in ("monthly",):
        send_monthly_report(dry_run=args.dry_run)
        log.info("月次レポート: 送信完了")


if __name__ == "__main__":
    main()
