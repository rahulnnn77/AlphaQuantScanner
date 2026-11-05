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

    def calc_adx(df, period=14):
        try:
            high = df["High"].dropna()
            low = df["Low"].dropna()
            close = df["Close"].dropna()
            if len(close) < period * 2:
                return 0.0
            up_move = high.diff()
            down_move = -low.diff()
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.ewm(alpha=1/period, adjust=False).mean()
            plus_di = 100 * (pd.Series(plus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean() / atr)
            minus_di = 100 * (pd.Series(minus_dm, index=high.index).ewm(alpha=1/period, adjust=False).mean() / atr)
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
            adx = dx.ewm(alpha=1/period, adjust=False).mean()
            val = float(adx.iloc[-1])
            return round(val, 2) if not np.isnan(val) else 0.0
        except Exception:
            return 0.0

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
        adx_val = calc_adx(df)

        if broken_above:
            return {"status": "BROKEN_ABOVE", "action": "Bullish Breakout", "ltp": round(last_c, 2), "diff_pct": diff_pct, "adx": adx_val}
        elif broken_below:
            return {"status": "BROKEN_BELOW", "action": "Bearish Breakdown", "ltp": round(last_c, 2), "diff_pct": diff_pct, "adx": adx_val}
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
                        try:
                            import pytz
                            ist_tz = pytz.timezone("Asia/Kolkata")
                            if hdf.index.tz is None:
                                hdf.index = hdf.index.tz_localize("UTC").tz_convert(ist_tz)
                            else:
                                hdf.index = hdf.index.tz_convert(ist_tz)
                        except Exception:
                            pass
                        df4h = hdf.resample("4h", origin="start_day", offset="9h15min").agg(
                            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
                        ).dropna()
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
    save_hps_selected_top3_fo_history(all_results)

def save_hps_selected_top3_fo_history(all_results):
    """
    Saves the Top 3 F&O HPS Selected stocks per timeframe (4h, daily, weekly, monthly)
    ranked by timeframe-specific ADX(14) with Date & Time (IST), and retains only the last 7 days (1 week).
    """
    try:
        from datetime import datetime, timedelta
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist)
        slot_minute = 30 if now_ist.minute >= 30 else 0
        slot_dt = now_ist.replace(minute=slot_minute, second=0, microsecond=0)
        slot_id = slot_dt.strftime("%Y-%m-%d %H:%M")
        date_str = now_ist.strftime("%Y-%m-%d")
        time_str = now_ist.strftime("%I:%M %p IST")
        display_dt = now_ist.strftime("%d %b %Y, %I:%M %p IST")
        epoch_ts = int(now_ist.timestamp())

        top3_by_tf = {}
        for tf_key in ["4h", "daily", "weekly", "monthly"]:
            items = all_results.get(tf_key, [])
            fo_only = [dict(x) for x in items if x.get("is_fo")]
            ranked = sorted(fo_only, key=lambda x: float(x.get("adx") or 0.0), reverse=True)[:3]
            cleaned = []
            for idx, stk in enumerate(ranked):
                cleaned.append({
                    "rank": idx + 1,
                    "symbol": stk.get("symbol"),
                    "name": stk.get("name"),
                    "industry": stk.get("industry", "Equities"),
                    "is_fo": True,
                    "timeframe": tf_key.upper(),
                    "status": stk.get("status"),
                    "action": stk.get("action"),
                    "saved_ltp": round(float(stk.get("ltp") or 0.0), 2),
                    "saved_spread_pct": round(float(stk.get("diff_pct") or 0.0), 2),
                    "adx": round(float(stk.get("adx") or 0.0), 2),
                    "date": date_str,
                    "time": time_str,
                    "slot_id": slot_id,
                    "saved_at": display_dt
                })
            top3_by_tf[tf_key] = cleaned

        history_file = os.path.join(BASE_DIR, "hps_selected_top3_history.json")
        existing_snapshots = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    loaded = json.load(f)
                    existing_snapshots = loaded.get("snapshots", [])
            except Exception:
                existing_snapshots = []

        # Remove any existing snapshot for the same 30-min slot_id so re-runs within the same slot update cleanly
        cutoff_ts = int((now_ist - timedelta(days=7)).timestamp())
        filtered_snapshots = [
            s for s in existing_snapshots
            if s.get("slot_id") != slot_id and int(s.get("timestamp", 0)) >= cutoff_ts
        ]

        new_snapshot = {
            "slot_id": slot_id,
            "date": date_str,
            "time": time_str,
            "saved_at": display_dt,
            "timestamp": epoch_ts,
            "universe": "NIFTY F&O",
            "top3": top3_by_tf
        }
        filtered_snapshots.insert(0, new_snapshot)
        filtered_snapshots.sort(key=lambda s: int(s.get("timestamp", 0)), reverse=True)

        with open(history_file, "w") as f:
            json.dump({
                "last_updated": display_dt,
                "retention_days": 7,
                "universe": "NIFTY F&O",
                "total_snapshots": len(filtered_snapshots),
                "snapshots": filtered_snapshots
            }, f, indent=2)
        logger.info(f"Saved HPS Selected Top 3 F&O snapshot for {slot_id} (Total 7-day snapshots: {len(filtered_snapshots)})")
    except Exception as e:
        logger.error(f"Error saving HPS Selected Top 3 F&O history: {e}")

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

def broadcast_scan_summary_to_telegram(force_send: bool = False):
    """
    Sends automated alerts for breakout stocks across 4H, Daily, Weekly, and Monthly
    explicitly mentioning the Timeframe and F&O segment tag.
    If force_send=True, dispatches immediately even if automated schedule is paused.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.entities import TelegramSettings, User
        import requests, pytz
        from datetime import datetime

        db = SessionLocal()
        settings = db.query(TelegramSettings).first()
        if not settings or not settings.bot_token:
            db.close()
            return {"status": "error", "message": "Telegram Bot Token is not configured."}
        if not force_send and not settings.is_enabled:
            db.close()
            return {"status": "paused", "message": "Telegram automated notifications are paused."}

        # Enforce 1-hour interval for scheduled automated alerts (while allowing force_send immediately)
        last_sent_file = os.path.join(BASE_DIR, "telegram_last_broadcast.json")
        now_epoch = time.time()
        if not force_send and os.path.exists(last_sent_file):
            try:
                with open(last_sent_file, "r") as lf:
                    last_ts = float(json.load(lf).get("last_sent_ts", 0))
                if (now_epoch - last_ts) < 3300:  # ~55 minutes threshold so 60-min cron slots fire cleanly
                    logger.info("Skipping Telegram broadcast (1-hour alert interval not elapsed yet).")
                    db.close()
                    return {"status": "skipped", "message": "Skipped (1-hour alert interval not elapsed yet)."}
            except Exception:
                pass

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
        sent_count = 0
        for cid in chat_ids:
            try:
                r = requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=8)
                if r.status_code == 200:
                    sent_count += 1
            except Exception as e:
                logger.warning(f"Error sending to {cid}: {e}")

        db.close()
        try:
            with open(last_sent_file, "w") as lf:
                json.dump({"last_sent_ts": now_epoch, "last_sent_ist": now_str}, lf)
        except Exception:
            pass
        logger.info(f"Broadcasted scan summary to {sent_count}/{len(chat_ids)} chats.")
        return {"status": "success", "sent_count": sent_count, "total_targets": len(chat_ids), "message": f"Broadcasted live HPS scan summary to {sent_count} Telegram recipient(s)."}
    except Exception as e:
        logger.error(f"Error broadcasting scan summary to Telegram: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    t0 = time.time()
    try:
        from app.services.dhan_service import DhanClientService
        DhanClientService.ensure_valid_session()
    except Exception as e:
        logger.warning(f"Dhan health check in scanner job returned: {e}")
    try:
        from app.services.screener_engine import ScreenerEngine
        ScreenerEngine.get_weekly_position_strategy(force_refresh=True)
        logger.info("Evaluated Nifty 50 Weekly Position Strategy & Telegram alerts.")
    except Exception as e:
        logger.warning(f"Weekly Position evaluation in scanner job returned: {e}")
    run_hps_breakout_scan()
    run_mean_reversion_scan()
    broadcast_scan_summary_to_telegram()
    logger.info(f"Full scanner update finished in {round(time.time() - t0, 1)}s")
