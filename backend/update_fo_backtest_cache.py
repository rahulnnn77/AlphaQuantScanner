import os
import json
import urllib.request
import urllib.parse
import concurrent.futures
import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fo_backtest_cache")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend", "dist")
CACHE_JSON_PATH = os.path.join(DIST_DIR, "fo_backtest_data.json")
PREVIEW_HTML_PATH = os.path.join(DIST_DIR, "backtest_preview.html")
STAMP_FILE = os.path.join(BASE_DIR, "data", "last_fo_backtest_eod_date.txt")


def update_fo_backtest_eod_cache(force: bool = False) -> bool:
    """
    Runs once per trading day after NSE close (15:45 IST) to refresh the 5-year daily
    OHLCV cache for all 213 Nifty F&O stocks + benchmarks.
    """
    now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    today_str = now_ist.strftime("%Y-%m-%d")

    if not force:
        # Never run during live NSE market hours (09:15 - 15:40 IST) to ensure 0% market-hour server load
        if now_ist.weekday() < 5 and (9 <= now_ist.hour < 15 or (now_ist.hour == 15 and now_ist.minute < 40)):
            return False
        if os.path.exists(STAMP_FILE):
            try:
                with open(STAMP_FILE, "r") as f:
                    if f.read().strip() == today_str:
                        return False
            except Exception:
                pass

    fo_path = os.path.join(BASE_DIR, "fo_symbols.json")
    meta_path = os.path.join(BASE_DIR, "nifty500_meta.json")
    if not os.path.exists(fo_path):
        return False

    with open(fo_path, "r") as f:
        fo_syms = json.load(f)
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)

    existing = {}
    if os.path.exists(CACHE_JSON_PATH):
        try:
            with open(CACHE_JSON_PATH, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    benchmarks = [
        ("^NSEI", "NIFTY50", "NIFTY 50 Index", "Index"),
        ("^CRSLDX", "NIFTY500", "NIFTY 500 Index", "Index"),
        ("^NSEBANK", "BANKNIFTY", "NIFTY Bank Index", "Index"),
    ]
    tasks = list(benchmarks) + [
        (f"{s}.NS", s, meta.get(s, {}).get("name", s), meta.get(s, {}).get("industry", "Nifty F&O"))
        for s in fo_syms
    ]

    def fetch_one(item):
        yf_sym, sym, name, sec = item
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yf_sym)}?range=5y&interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read().decode())
            res = d["chart"]["result"][0]
            ts = res["timestamp"]
            q = res["indicators"]["quote"][0]
            candles = []
            for i in range(len(ts)):
                o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
                if o is None or h is None or l is None or c is None or c <= 0:
                    continue
                dt = datetime.datetime.fromtimestamp(ts[i] + 19800, datetime.timezone.utc).strftime("%Y-%m-%d")
                candles.append([dt, round(o, 2), round(h, 2), round(l, 2), round(c, 2), int(v or 0)])
            return sym, {
                "symbol": sym,
                "name": name,
                "sector": sec,
                "is_ipo": False,
                "is_fo": True,
                "candles": candles,
            }
        except Exception:
            return sym, existing.get(sym)

    out = dict(existing)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for sym, data in ex.map(fetch_one, tasks):
            if data and len(data.get("candles", [])) > 65:
                out[sym] = data

    os.makedirs(DIST_DIR, exist_ok=True)
    json_str = json.dumps(out, separators=(",", ":"))
    with open(CACHE_JSON_PATH, "w") as f:
        f.write(json_str)

    if os.path.exists(PREVIEW_HTML_PATH):
        try:
            with open(PREVIEW_HTML_PATH, "r") as f:
                html = f.read()
            s_md = html.find("const MARKET_DATA = ")
            e_md = html.find(";\n\n    let CONDITION_LOGIC", s_md)
            if s_md != -1 and e_md != -1:
                html = html[:s_md] + "const MARKET_DATA = " + json_str + html[e_md:]
                with open(PREVIEW_HTML_PATH, "w") as f:
                    f.write(html)
        except Exception as e:
            logger.warning(f"Could not update inline preview data: {e}")

    os.makedirs(os.path.dirname(STAMP_FILE), exist_ok=True)
    with open(STAMP_FILE, "w") as f:
        f.write(today_str)

    logger.info(f"Updated EOD Nifty F&O backtest cache ({len(out)} instruments) for {today_str}.")
    return True


if __name__ == "__main__":
    update_fo_backtest_eod_cache(force=True)

