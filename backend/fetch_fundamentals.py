import json
import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fundamentals_sync")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SYMBOLS_PATH = os.path.join(BASE_DIR, "nifty500_symbols.json")
META_PATH = os.path.join(BASE_DIR, "nifty500_meta.json")
CACHE_OUTPUT_PATH = os.path.join(BASE_DIR, "data", "fundamentals_cache.json")

# Ensure data directory exists
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

def safe_round(val, decimals=2):
    if val is None:
        return None
    try:
        return round(float(val), decimals)
    except (ValueError, TypeError):
        return None

def fetch_single_ticker(symbol, meta_info):
    yf_symbol = f"{symbol}.NS"
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}
        
        # Fundamental Ratios
        pe = safe_round(info.get("trailingPE"))
        forward_pe = safe_round(info.get("forwardPE"))
        pb = safe_round(info.get("priceToBook"))
        peg = safe_round(info.get("pegRatio"))
        roe = safe_round((info.get("returnOnEquity") or 0) * 100) if info.get("returnOnEquity") is not None else None
        roa = safe_round((info.get("returnOnAssets") or 0) * 100) if info.get("returnOnAssets") is not None else None
        operating_margin = safe_round((info.get("operatingMargins") or 0) * 100) if info.get("operatingMargins") is not None else None
        profit_margin = safe_round((info.get("profitMargins") or 0) * 100) if info.get("profitMargins") is not None else None
        
        # Debt and Balance Sheet Strength
        debt_to_equity = safe_round(info.get("debtToEquity"))
        current_ratio = safe_round(info.get("currentRatio"))
        free_cash_flow = info.get("freeCashflow")
        
        # Size and Valuation
        market_cap = info.get("marketCap")
        ev_to_ebitda = safe_round(info.get("enterpriseToEbitda"))
        dividend_yield = safe_round(info.get("dividendYield"))
        if dividend_yield and dividend_yield < 0.2:
            dividend_yield = safe_round(dividend_yield * 100)
            
        ltp = safe_round(info.get("currentPrice") or info.get("regularMarketPrice"))
        day_high = safe_round(info.get("dayHigh"))
        day_low = safe_round(info.get("dayLow"))
        high_52 = safe_round(info.get("fiftyTwoWeekHigh"))
        low_52 = safe_round(info.get("fiftyTwoWeekLow"))
        
        # Category by Market Cap (INR Cr)
        # 1 Cr = 10,000,000
        market_cap_cr = safe_round(market_cap / 10000000, 1) if market_cap else None
        cap_category = "Small Cap"
        if market_cap_cr:
            if market_cap_cr >= 20000:
                cap_category = "Large Cap"
            elif market_cap_cr >= 5000:
                cap_category = "Mid Cap"
                
        return {
            "symbol": symbol,
            "name": meta_info.get("name", symbol),
            "industry": meta_info.get("industry", "Diversified"),
            "sector": info.get("sector") or meta_info.get("industry", "Equities"),
            "ltp": ltp,
            "market_cap_cr": market_cap_cr,
            "cap_category": cap_category,
            "pe": pe,
            "forward_pe": forward_pe,
            "pb": pb,
            "peg": peg,
            "roe": roe,
            "roa": roa,
            "operating_margin": operating_margin,
            "profit_margin": profit_margin,
            "debt_to_equity": debt_to_equity,
            "current_ratio": current_ratio,
            "ev_to_ebitda": ev_to_ebitda,
            "dividend_yield": dividend_yield,
            "high_52": high_52,
            "low_52": low_52
        }
    except Exception as e:
        logger.debug(f"Failed to fetch {symbol}: {e}")
        return {
            "symbol": symbol,
            "name": meta_info.get("name", symbol),
            "industry": meta_info.get("industry", "Diversified"),
            "sector": meta_info.get("industry", "Equities"),
            "ltp": None,
            "market_cap_cr": None,
            "cap_category": "Mid Cap",
            "pe": None,
            "forward_pe": None,
            "pb": None,
            "peg": None,
            "roe": None,
            "roa": None,
            "operating_margin": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "current_ratio": None,
            "ev_to_ebitda": None,
            "dividend_yield": None,
            "high_52": None,
            "low_52": None
        }

def run_fundamentals_sync(limit=None):
    logger.info("Starting Fundamentals Data Sync...")
    with open(SYMBOLS_PATH, "r") as f:
        symbols = json.load(f)
    with open(META_PATH, "r") as f:
        meta = json.load(f)

    if limit:
        symbols = symbols[:limit]

    results = []
    # 8 worker threads for low memory usage and safe rate limiting
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_single_ticker, s, meta.get(s, {})): s for s in symbols}
        count = 0
        for future in as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
            count += 1
            if count % 50 == 0:
                logger.info(f"Processed {count}/{len(symbols)} fundamental records...")

    # Sort alphabetically by symbol
    results.sort(key=lambda x: x["symbol"])

    payload = {
        "status": "success",
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S IST"),
        "total_stocks": len(results),
        "stocks": results
    }

    with open(CACHE_OUTPUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"Fundamentals sync complete! Cached {len(results)} stocks to {CACHE_OUTPUT_PATH}")
    return payload

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_fundamentals_sync(limit=limit)
