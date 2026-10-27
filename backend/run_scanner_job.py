import json, time, os, sys, logging
import yfinance as yf
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scanner_job")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_hps_breakout_scan():
    logger.info("Starting HPS Breakout scan...")
    symbols_path = os.path.join(BASE_DIR, "nifty500_symbols.json")
    fo_path = os.path.join(BASE_DIR, "fo_symbols.json")
    meta_path = os.path.join(BASE_DIR, "nifty500_meta.json")

    with open(symbols_path) as f:
        symbols = [s for s in json.load(f) if s != "DUMMYHEG"]
    with open(fo_path) as f:
        fo_set = set(json.load(f))
    with open(meta_path) as f:
        meta = json.load(f)

    all_results = {"4h": [], "daily": [], "weekly": [], "monthly": []}

    def analyze_series(df, span=63):
        if df is None:
            return None
        close = df["Close"].dropna()
        if len(close) < span + 2:
            return None
        ema = close.ewm(span=span, adjust=False).mean()
        last_c = float(close.iloc[-1])
        prev_c = float(close.iloc[-2])
        last_e = float(ema.iloc[-1])
        prev_e = float(ema.iloc[-2])

        broken_above = (prev_c <= prev_e) and (last_c > last_e)
        broken_below = (prev_c >= prev_e) and (last_c < last_e)
        diff_pct = round(((last_c - last_e) / last_e) * 100, 2)

        if broken_above:
            return {"status": "BROKEN_ABOVE", "action": "Bullish Breakout", "ltp": round(last_c, 2), "diff_pct": diff_pct}
        elif broken_below:
            return {"status": "BROKEN_BELOW", "action": "Bearish Breakdown", "ltp": round(last_c, 2), "diff_pct": diff_pct}
        return None

    batch_size = 75
    for b_idx in range(0, len(symbols), batch_size):
        batch = symbols[b_idx:b_idx+batch_size]
        tickers = " ".join([f"{s}.NS" for s in batch])
        try:
            d_data = yf.download(tickers=tickers, period="1y", interval="1d", group_by="ticker", threads=True, progress=False)
            w_data = yf.download(tickers=tickers, period="2y", interval="1wk", group_by="ticker", threads=True, progress=False)
            m_data = yf.download(tickers=tickers, period="5y", interval="1mo", group_by="ticker", threads=True, progress=False)
            h_data = yf.download(tickers=tickers, period="60d", interval="1h", group_by="ticker", threads=True, progress=False)

            for s in batch:
                col = f"{s}.NS"
                name = meta.get(s, {}).get("name", s)
                industry = meta.get(s, {}).get("industry", "Equities")
                is_fo = (s in fo_set)

                if col in d_data:
                    r = analyze_series(d_data[col])
                    if r:
                        r.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        all_results["daily"].append(r)

                if col in w_data:
                    r = analyze_series(w_data[col])
                    if r:
                        r.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        all_results["weekly"].append(r)

                if col in m_data:
                    r = analyze_series(m_data[col])
                    if r:
                        r.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        all_results["monthly"].append(r)

                if col in h_data:
                    hdf = h_data[col].dropna()
                    if len(hdf) > 65:
                        df4h = hdf.resample("4h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}).dropna()
                        r = analyze_series(df4h)
                        if r:
                            r.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                            all_results["4h"].append(r)
        except Exception as e:
            logger.error(f"Error processing batch {b_idx}: {e}")

    cache_file = os.path.join(BASE_DIR, "hps_screener_cache.json")
    with open(cache_file, "w") as f:
        json.dump({
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S IST"),
            "results": all_results
        }, f, indent=2)
    logger.info("Saved fresh HPS Breakout cache.")

def run_mean_reversion_scan():
    logger.info("Starting HPS Mean Reversion scan...")
    symbols_path = os.path.join(BASE_DIR, "nifty500_symbols.json")
    fo_path = os.path.join(BASE_DIR, "fo_symbols.json")
    meta_path = os.path.join(BASE_DIR, "nifty500_meta.json")

    with open(symbols_path) as f:
        symbols = [s for s in json.load(f) if s != "DUMMYHEG"]
    with open(fo_path) as f:
        fo_set = set(json.load(f))
    with open(meta_path) as f:
        meta = json.load(f)

    mr_results = {
        "daily": {"level1": [], "level2": [], "level3": []},
        "weekly": {"level1": [], "level2": [], "level3": []},
        "monthly": {"level1": [], "level2": [], "level3": []}
    }

    def check_mean_reversion_levels(close_series):
        if close_series is None or len(close_series) < 205:
            return {}
        last_c = float(close_series.iloc[-1])
        found_levels = {}

        ema200 = float(close_series.ewm(span=200, adjust=False).mean().iloc[-1])
        diff1_pct = round(((last_c - ema200) / ema200) * 100, 2)
        if abs(diff1_pct) <= 2.0:
            found_levels["level1"] = {
                "level": "Level-1",
                "level_name": "Level-1",
                "ltp": round(last_c, 2),
                "spread_pct": diff1_pct,
                "status": "At Support Level" if diff1_pct >= 0 else "Testing Level"
            }

        if len(close_series) >= 305:
            sma300 = float(close_series.rolling(window=300).mean().iloc[-1])
            if not np.isnan(sma300):
                diff2_pct = round(((last_c - sma300) / sma300) * 100, 2)
                if abs(diff2_pct) <= 2.0:
                    found_levels["level2"] = {
                        "level": "Level-2",
                        "level_name": "Level-2",
                        "ltp": round(last_c, 2),
                        "spread_pct": diff2_pct,
                        "status": "At Support Level" if diff2_pct >= 0 else "Testing Level"
                    }

        if len(close_series) >= 505:
            sma500 = float(close_series.rolling(window=500).mean().iloc[-1])
            if not np.isnan(sma500):
                diff3_pct = round(((last_c - sma500) / sma500) * 100, 2)
                if abs(diff3_pct) <= 2.0:
                    found_levels["level3"] = {
                        "level": "Level-3",
                        "level_name": "Level-3",
                        "ltp": round(last_c, 2),
                        "spread_pct": diff3_pct,
                        "status": "At Support Level" if diff3_pct >= 0 else "Testing Level"
                    }
        return found_levels

    batch_size = 75
    for b_idx in range(0, len(symbols), batch_size):
        batch = symbols[b_idx:b_idx+batch_size]
        tickers = " ".join([f"{s}.NS" for s in batch])
        try:
            d_data = yf.download(tickers=tickers, period="2y", interval="1d", group_by="ticker", threads=True, progress=False)
            w_data = yf.download(tickers=tickers, period="5y", interval="1wk", group_by="ticker", threads=True, progress=False)
            m_data = yf.download(tickers=tickers, period="10y", interval="1mo", group_by="ticker", threads=True, progress=False)

            for s in batch:
                col = f"{s}.NS"
                name = meta.get(s, {}).get("name", s)
                industry = meta.get(s, {}).get("industry", "Equities")
                is_fo = (s in fo_set)

                if col in d_data:
                    c = d_data[col]["Close"].dropna()
                    lvls = check_mean_reversion_levels(c)
                    for l_key, obj in lvls.items():
                        obj.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        mr_results["daily"][l_key].append(obj)

                if col in w_data:
                    c = w_data[col]["Close"].dropna()
                    lvls = check_mean_reversion_levels(c)
                    for l_key, obj in lvls.items():
                        obj.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        mr_results["weekly"][l_key].append(obj)

                if col in m_data:
                    c = m_data[col]["Close"].dropna()
                    lvls = check_mean_reversion_levels(c)
                    for l_key, obj in lvls.items():
                        obj.update({"symbol": s, "name": name, "industry": industry, "is_fo": is_fo})
                        mr_results["monthly"][l_key].append(obj)
        except Exception as e:
            logger.error(f"Error processing MR batch {b_idx}: {e}")

    cache_file = os.path.join(BASE_DIR, "hps_mean_reversion_cache.json")
    with open(cache_file, "w") as f:
        json.dump({
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S IST"),
            "results": mr_results
        }, f, indent=2)
    logger.info("Saved fresh HPS Mean Reversion cache.")

def broadcast_scan_summary_to_telegram():
    """
    Sends automated alerts for breakout stocks across 4H, Daily, Weekly, and Monthly
    explicitly mentioning the Timeframe and F&O segment tag.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.entities import TelegramSettings, User
        import requests, pytz
        from datetime import datetime

        db = SessionLocal()
        settings = db.query(TelegramSettings).first()
        if not settings or not settings.is_enabled or not settings.bot_token:
            db.close()
            return

        cache_file = os.path.join(BASE_DIR, "hps_screener_cache.json")
        if not os.path.exists(cache_file):
            db.close()
            return

        with open(cache_file, "r") as f:
            hps_data = json.load(f).get("results", {})

        ist = pytz.timezone("Asia/Kolkata")
        now_str = datetime.now(ist).strftime("%d %b %Y, %I:%M %p IST")

        # 1. Prepare message with explicit Timeframes and F&O tags
        lines = [
            "<b>AlphaQuant Screener Alert</b>",
            f"<b>Session:</b> {now_str}",
            "<b>Scan Type:</b> HPS Breakout & Breakdown (Multi-Timeframe)",
            ""
        ]

        tf_labels = {
            "daily": "Daily (1D Trend)",
            "4h": "4-Hour (4H Swing)",
            "weekly": "Weekly (1W Positional)",
            "monthly": "Monthly (1M Macro)"
        }

        has_stocks = False
        for tf in ["daily", "weekly", "4h", "monthly"]:
            items = hps_data.get(tf, [])
            fo_stocks = [s for s in items if s.get("is_fo")]
            other_stocks = [s for s in items if not s.get("is_fo")]

            bullish = [s for s in (fo_stocks + other_stocks) if s.get("status") == "BROKEN_ABOVE"][:3]
            bearish = [s for s in (fo_stocks + other_stocks) if s.get("status") == "BROKEN_BELOW"][:3]

            if not bullish and not bearish:
                continue

            has_stocks = True
            lines.append(f"<b>[{tf_labels.get(tf, tf.upper())}]</b>")
            if bullish:
                lines.append("  <b>Bullish Breakout:</b>")
                for s in bullish:
                    tag = " [F&amp;O]" if s.get("is_fo") else ""
                    lines.append(f"   • <code>{s['symbol']}</code>: ₹{s.get('ltp', 0.0):,.2f} (+{s.get('diff_pct', 0.0):.2f}%){tag}")
            if bearish:
                lines.append("  <b>Bearish Breakdown:</b>")
                for s in bearish:
                    tag = " [F&amp;O]" if s.get("is_fo") else ""
                    lines.append(f"   • <code>{s['symbol']}</code>: ₹{s.get('ltp', 0.0):,.2f} ({s.get('diff_pct', 0.0):.2f}%){tag}")
            lines.append("")

        if not has_stocks:
            db.close()
            return

        lines.append("<i>Live scan from AlphaQuant Terminal</i>")
        msg = "\n".join(lines)

        # Recipients
        users = db.query(User).filter(
            User.telegram_chat_id.isnot(None),
            User.is_active == True,
            User.telegram_alerts_enabled == True
        ).all()

        chat_ids = set()
        if settings.default_channel_id:
            chat_ids.add(settings.default_channel_id)
        for u in users:
            chat_ids.add(u.telegram_chat_id)

        url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
        for cid in chat_ids:
            try:
                requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=8)
            except Exception as e:
                logger.warning(f"Error sending to {cid}: {e}")

        db.close()
        logger.info(f"Broadcasted scan summary to {len(chat_ids)} chats.")
    except Exception as e:
        logger.error(f"Error broadcasting scan summary to Telegram: {e}")

if __name__ == "__main__":
    t0 = time.time()
    run_hps_breakout_scan()
    run_mean_reversion_scan()
    broadcast_scan_summary_to_telegram()
    logger.info(f"Full scanner update finished in {round(time.time() - t0, 1)}s")
