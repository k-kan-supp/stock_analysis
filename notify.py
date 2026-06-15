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
WATCHLIST = [c.strip() for c in os.getenv("WATCHLIST_CODES", "").split(",") if c.strip()]
RSI_HIGH  = float(os.getenv("RSI_HIGH", "70"))
RSI_LOW   = float(os.getenv("RSI_LOW",  "30"))

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
                "price":        float(r["price_latest"]) if r["price_latest"] else None,
                "daily_return": float(r["daily_return"]) if r["daily_return"] else None,
            })

    if not triggered:
        log.info("SPC アラート: 新規アラートなし")
        return []

    def _badge(label: str) -> str:
        color = _SPC_COLORS.get(label, "#333")
        return f"<span style='color:{color};font-weight:bold'>{label}</span>"

    rows_html = "".join(
        f"<tr style='background:#{'fff9f0' if t['label'] in ('Target超え','連続上昇') else 'f0f4ff'}'>"
        f"<td>{t['code']}</td><td>{t['name']}</td>"
        f"<td>{_badge(t['label'])}</td>"
        f"<td style='text-align:center'><b>{t['days']}日</b></td>"
        f"<td style='text-align:right'>¥{t['price']:,.0f}</td>"
        f"<td style='text-align:right'>{(t['daily_return'] * 100):.2f}%</td>"
        f"<td>{t['date']}</td></tr>"
        for t in triggered
        if t["price"] is not None and t["daily_return"] is not None
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
            _record_sent(
                t["code"], t["alert_type"], t["date"],
                f"{t['label']} {t['days']}日 ¥{t['price']:,.0f}",
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
        choices=["all", "cross", "price", "rsi", "spc", "report"],
        default="all",
        help="実行するアラート種別 (デフォルト: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="メール送信せずにログ出力のみ行う",
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


if __name__ == "__main__":
    main()
