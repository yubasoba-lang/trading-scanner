from datetime import datetime


def build_html_email(results, paper_summary, dashboard_url, starting_balance_jpy, usd_jpy_rate, risk_pct):
    now = datetime.now()
    date_str = now.strftime("%A, %b %d")
    time_str = now.strftime("%H:%M")

    bullish = [r for r in results if r.get("bias") == "BULLISH" and "error" not in r]
    bearish = [r for r in results if r.get("bias") == "BEARISH" and "error" not in r]
    neutral = [r for r in results if r.get("bias") == "NEUTRAL" and "error" not in r]

    closed = [t for t in paper_summary if t["status"] != "open"]
    wins = [t for t in closed if t["status"] == "target_hit"]
    losses = [t for t in closed if t["status"] == "stopped_out"]
    total_pnl = sum(t.get("result_pct", 0) for t in closed)
    win_rate = round(len(wins) / len(closed) * 100) if closed else 0
    account_usd = starting_balance_jpy / usd_jpy_rate
    current_jpy = round((account_usd * (1 + total_pnl / 100)) * usd_jpy_rate)
    pnl_jpy = current_jpy - starting_balance_jpy
    pnl_color = "#1a7a45" if pnl_jpy >= 0 else "#c0392b"
    pnl_str = f"+¥{pnl_jpy:,}" if pnl_jpy >= 0 else f"-¥{abs(pnl_jpy):,}"

    def signal_card(r):
        price = r["price"]
        atr_pct = r.get("atr_pct", 2.0)
        sl_pct = round(-(atr_pct * 1.5), 1)
        tp_pct = round(atr_pct * 2.5, 1)
        sl = round(price * (1 + sl_pct / 100), 2)
        tp = round(price * (1 + tp_pct / 100), 2)
        account_usd = starting_balance_jpy / usd_jpy_rate
        risk_usd = round(account_usd * risk_pct / 100, 2)
        position_usd = round(min(risk_usd / (abs(sl_pct) / 100), account_usd * 0.20), 2)
        shares = round(position_usd / price, 4)
        max_loss = round(position_usd * abs(sl_pct) / 100, 2)
        max_gain = round(position_usd * tp_pct / 100, 2)
        position_jpy = round(position_usd * usd_jpy_rate)

        rsi = r["rsi"]
        if rsi < 30: rsi_label = "oversold"
        elif rsi < 45: rsi_label = "recovering"
        elif rsi > 70: rsi_label = "overbought"
        elif rsi > 55: rsi_label = "heating up"
        else: rsi_label = "neutral"

        macd_std = r.get("macd_bullish", False)
        macd_fast = r.get("macd_fast_bullish", False)
        if macd_std and macd_fast:
            macd_label = "Bullish ↑ (both signals agree)"
            macd_color = "#1a7a45"
        elif macd_fast and not macd_std:
            macd_label = "Fast MACD bullish ↑ (early signal, higher risk)"
            macd_color = "#e67e22"
        elif macd_std and not macd_fast:
            macd_label = "Standard MACD bullish ↑"
            macd_color = "#1a7a45"
        else:
            macd_label = "Bearish crossover ↓"
            macd_color = "#c0392b"
        ema_trend = r.get("ema_trend", "—")
        vol = r.get("volume_ratio", 1.0)
        vol_label = f"{vol}x avg volume" + (" 🔥 HIGH" if vol > 1.5 else "")
        rr = round(tp_pct / abs(sl_pct), 1)

        indicators_html = f"""
            <tr style="border-top:1px solid #e8e8e8;background:#fafafa">
              <td colspan="3" style="padding:10px 16px">
                <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:12px">
                  <tr>
                    <td style="padding:3px 0;color:#999;width:100px">MACD</td>
                    <td style="padding:3px 0;color:{macd_color};font-weight:600">{macd_label}</td>
                    <td style="padding:3px 0;color:#999;width:100px">Volume</td>
                    <td style="padding:3px 0;color:#333">{vol_label}</td>
                  </tr>
                  <tr>
                    <td style="padding:3px 0;color:#999">EMA Trend</td>
                    <td style="padding:3px 0;color:#333">{ema_trend}</td>
                    <td style="padding:3px 0;color:#999">Risk/Reward</td>
                    <td style="padding:3px 0;color:#333">1:{rr}</td>
                  </tr>
                  <tr>
                    <td style="padding:3px 0;color:#999">ATR</td>
                    <td style="padding:3px 0;color:#333">{atr_pct}% avg daily move</td>
                  </tr>
                </table>
              </td>
            </tr>"""

        news_html = ""
        if r.get("news_summary"):
            news_html = f"""
            <tr><td colspan="3" style="padding:12px 16px;border-top:1px solid #e8e8e8;font-size:13px;color:#555;line-height:1.6">
              <span style="font-size:10px;color:#999;display:block;margin-bottom:4px;letter-spacing:1px">NEWS</span>
              {r['news_summary'].replace('#', '').replace('Summary', '').strip()}
            </td></tr>"""

        earnings_html = ""
        if r.get("earnings_warning"):
            earnings_html = f"""<div style="background:#fff8e1;border:1px solid #f9c642;border-radius:6px;padding:8px 12px;margin:12px 16px 0;font-size:12px;color:#7a5c00">
              ⚠ Earnings within 7 days — higher risk, consider skipping
            </div>"""

        return f"""
        <div style="border:1px solid #e0e0e0;border-radius:12px;overflow:hidden;margin-bottom:16px;background:#ffffff">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f7f8fa;border-collapse:collapse">
            <tr>
              <td style="padding:14px 16px;vertical-align:middle">
                <span style="font-size:20px;font-weight:700;color:#111">{r['ticker']}</span>
                <span style="font-size:13px;color:#999;margin-left:8px">${price}</span>
              </td>
              <td style="padding:14px 16px;text-align:right;vertical-align:middle">
                <span style="background:#e6f4ec;color:#1a7a45;font-size:11px;padding:3px 10px;border-radius:20px;border:1px solid #b2dfc4;white-space:nowrap">Score {r['score']}/100</span>
                <span style="background:#f0f0f0;color:#666;font-size:11px;padding:3px 10px;border-radius:20px;white-space:nowrap;margin-left:6px">RSI {rsi} · {rsi_label}</span>
              </td>
            </tr>
          </table>
          {earnings_html}
          <table style="width:100%;border-collapse:collapse;background:#ffffff">
            <tr style="border-top:1px solid #e8e8e8">
              <td style="padding:12px 16px;width:33%">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">ENTRY</div>
                <div style="font-size:15px;font-weight:700;color:#111">${price}</div>
              </td>
              <td style="padding:12px 16px;width:33%;border-left:1px solid #e8e8e8">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">STOP LOSS</div>
                <div style="font-size:15px;font-weight:700;color:#c0392b">${sl}</div>
                <div style="font-size:11px;color:#c0392b">{sl_pct}%</div>
              </td>
              <td style="padding:12px 16px;width:33%;border-left:1px solid #e8e8e8">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">TAKE PROFIT</div>
                <div style="font-size:15px;font-weight:700;color:#1a7a45">${tp}</div>
                <div style="font-size:11px;color:#1a7a45">+{tp_pct}%</div>
              </td>
            </tr>
            <tr style="border-top:1px solid #e8e8e8;background:#fafafa">
              <td style="padding:12px 16px">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">INVEST</div>
                <div style="font-size:14px;font-weight:700;color:#111">${position_usd}</div>
                <div style="font-size:11px;color:#999">~¥{position_jpy:,} · {shares} shares</div>
              </td>
              <td style="padding:12px 16px;border-left:1px solid #e8e8e8">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">MAX LOSS</div>
                <div style="font-size:14px;font-weight:700;color:#c0392b">-${max_loss}</div>
              </td>
              <td style="padding:12px 16px;border-left:1px solid #e8e8e8">
                <div style="font-size:10px;color:#999;margin-bottom:3px;letter-spacing:1px">MAX GAIN</div>
                <div style="font-size:14px;font-weight:700;color:#1a7a45">+${max_gain}</div>
              </td>
            </tr>
            {indicators_html}
            {news_html}
          </table>
        </div>"""

    def section(title, items, color):
        if not items:
            return ""
        cards = "".join(signal_card(r) for r in sorted(items, key=lambda x: x.get("score", 0), reverse=True))
        return f"""
        <div style="font-size:11px;color:{color};letter-spacing:1px;margin:24px 0 12px;font-weight:600">{title}</div>
        {cards}"""

    def watchlist_section(all_results):
        """Shown when nothing is bullish — top 5 by score so the email is never empty."""
        valid = [r for r in all_results if "error" not in r and r.get("bias") != "BULLISH"]
        top5 = sorted(valid, key=lambda x: x.get("score", 0), reverse=True)[:5]
        if not top5:
            return ""
        rows = "".join(f"""
        <tr style="border-bottom:1px solid #eeeeee">
          <td style="padding:10px 16px;font-weight:700;color:#111">{r['ticker']}</td>
          <td style="padding:10px 16px;color:#555">${r['price']}</td>
          <td style="padding:10px 16px;color:#555">{r['score']}/100</td>
          <td style="padding:10px 16px;color:#{'1a7a45' if r.get('macd_bullish') else 'c0392b'};font-size:12px">
            {'MACD ↑' if r.get('macd_bullish') else 'MACD ↓'} · RSI {r['rsi']}
          </td>
          <td style="padding:10px 16px;color:#999;font-size:12px">{r.get('ema_trend','—')} trend</td>
        </tr>""" for r in top5)
        return f"""
        <div style="font-size:11px;color:#888;letter-spacing:1px;margin:24px 0 12px;font-weight:600">── NO STRONG SETUPS TODAY — TOP WATCHLIST CANDIDATES</div>
        <div style="font-size:12px;color:#999;margin-bottom:10px">Nothing cleared the buy threshold. These are the closest — watch them for tomorrow.</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border-radius:12px;border:1px solid #e0e0e0;overflow:hidden">
          <tr style="border-bottom:1px solid #eeeeee;background:#f9f9f9">
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">TICKER</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">PRICE</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">SCORE</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">MOMENTUM</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">TREND</th>
          </tr>
          {rows}
        </table>"""

    bearish_rows = "".join(f"""
        <tr style="border-bottom:1px solid #eeeeee">
          <td style="padding:10px 16px;font-weight:700;color:#111">{r['ticker']}</td>
          <td style="padding:10px 16px;color:#555">${r['price']}</td>
          <td style="padding:10px 16px;color:#555">{r['score']}/100</td>
          <td style="padding:10px 16px;color:#c0392b">RSI {r['rsi']}</td>
          <td style="padding:10px 16px;color:#999;font-size:12px">Avoid / exit if holding</td>
        </tr>""" for r in bearish)

    bearish_section = f"""
        <div style="font-size:11px;color:#c0392b;letter-spacing:1px;margin:24px 0 12px;font-weight:600">▼ BEARISH — AVOID OR EXIT IF HOLDING</div>
        <table style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;border-radius:12px;border:1px solid #e0e0e0;overflow:hidden">
          <tr style="border-bottom:1px solid #eeeeee;background:#fdf5f5">
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">TICKER</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">PRICE</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">SCORE</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">RSI</th>
            <th style="padding:10px 16px;text-align:left;font-size:10px;color:#999;font-weight:500;letter-spacing:1px">ACTION</th>
          </tr>
          {bearish_rows}
        </table>""" if bearish else ""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f3f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f3f5;min-height:100vh">
  <tr><td>
  <div style="max-width:560px;margin:0 auto;padding:16px">

    <!-- Header -->
    <div style="background:#111;border-radius:12px;padding:20px 24px;margin-bottom:16px">
      <div style="font-size:11px;color:#888;letter-spacing:2px;margin-bottom:6px">TRADING SCANNER</div>
      <div style="font-size:24px;font-weight:700;color:#f5f0e8">{date_str}</div>
      <div style="font-size:12px;color:#666;margin-top:4px">{len(results)} tickers scanned · {time_str} · Market opens 3:30pm HU</div>
    </div>

    <!-- Paper account summary -->
    <div style="background:#ffffff;border-radius:12px;padding:16px 24px;margin-bottom:16px;border:1px solid #e0e0e0">
      <div style="font-size:10px;color:#999;letter-spacing:1px;margin-bottom:12px;font-weight:600">PAPER ACCOUNT</div>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
        <tr>
          <td style="vertical-align:bottom">
            <div style="font-size:22px;font-weight:700;color:#111">¥{current_jpy:,}</div>
            <div style="font-size:12px;color:{pnl_color};margin-top:2px">{pnl_str} since start</div>
          </td>
          <td width="70" style="text-align:center;vertical-align:bottom">
            <div style="font-size:18px;font-weight:700;color:#111">{win_rate}%</div>
            <div style="font-size:11px;color:#999">Win rate</div>
          </td>
          <td width="50" style="text-align:center;vertical-align:bottom">
            <div style="font-size:18px;font-weight:700;color:#1a7a45">{len(wins)}</div>
            <div style="font-size:11px;color:#999">Wins</div>
          </td>
          <td width="55" style="text-align:center;vertical-align:bottom">
            <div style="font-size:18px;font-weight:700;color:#c0392b">{len(losses)}</div>
            <div style="font-size:11px;color:#999">Losses</div>
          </td>
        </tr>
      </table>
    </div>

    <!-- Signals -->
    {section("▲ BULLISH SETUPS — CONSIDER BUYING", bullish, "#1a7a45")}
    {watchlist_section(results) if not bullish else ""}
    {bearish_section}

    <!-- How to use -->
    <div style="background:#ffffff;border-radius:12px;padding:16px 24px;margin-top:24px;border:1px solid #e0e0e0">
      <div style="font-size:10px;color:#999;letter-spacing:1px;margin-bottom:12px;font-weight:600">HOW TO USE THIS EMAIL</div>
      <ol style="margin:0;padding-left:20px;color:#444;font-size:13px;line-height:2">
        <li>Look at bullish setups only</li>
        <li>Pick 1–2 with the highest score</li>
        <li>Open your broker at market open (3:30pm HU)</li>
        <li>Place buy order at entry price</li>
        <li>Set stop loss and take profit levels</li>
        <li>Walk away — broker handles the rest</li>
      </ol>
    </div>

    <!-- CTA -->
    <div style="text-align:center;margin:24px 0">
      <a href="{dashboard_url}" style="display:inline-block;background:#111;color:#fff;padding:14px 36px;border-radius:10px;font-weight:700;font-size:15px;text-decoration:none">Log my decisions</a>
      <div style="font-size:12px;color:#999;margin-top:8px">Tap Buy / Skip / Watch for each signal and write your reasoning</div>
    </div>

    <!-- Footer -->
    <div style="text-align:center;font-size:11px;color:#bbb;padding:16px 0">
      Paper trades only. Not financial advice.
    </div>
  </div>
  </td></tr></table>
</body>
</html>"""

    return html
