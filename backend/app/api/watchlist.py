import time as time_mod
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import User, Watchlist, WatchlistStock
from app.api.deps import get_current_user
from app.services.screener_engine import ScreenerEngine, NIFTY_50_STOCKS

logger = logging.getLogger("watchlist_api")
router = APIRouter()

# ----------------- SHARED IN-MEMORY QUOTE & BENCHMARK CACHE ----------------- #
_QUOTE_CACHE: Dict[str, Dict[str, Any]] = {}
_QUOTE_CACHE_TS: Dict[str, float] = {}

_SEARCH_CACHE: Dict[str, Dict[str, Any]] = {}
_HISTORY_CACHE: Dict[str, Dict[str, Any]] = {}

TIMEFRAME_KEYS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y"]

# Benchmark & Sectoral Index definitions (all fetched in one combined batch request)
SECTOR_BENCHMARKS: Dict[str, Dict[str, str]] = {
    "Banking": {
        "sector": "Banking",
        "index_name": "Nifty Bank",
        "tv_ticker": "NSE:BANKNIFTY",
        "yf_symbol": "^NSEBANK",
    },
    "Financial Services": {
        "sector": "Financial Services",
        "index_name": "Nifty Fin Service",
        "tv_ticker": "NSE:CNXFINANCE",
        "yf_symbol": "NIFTY_FIN_SERVICE.NS",
    },
    "IT": {
        "sector": "IT",
        "index_name": "Nifty IT",
        "tv_ticker": "NSE:CNXIT",
        "yf_symbol": "^CNXIT",
    },
    "Automobile": {
        "sector": "Automobile",
        "index_name": "Nifty Auto",
        "tv_ticker": "NSE:AUTOBEES",
        "yf_symbol": "^CNXAUTO",
    },
    "Pharma": {
        "sector": "Pharma",
        "index_name": "Nifty Pharma",
        "tv_ticker": "NSE:PHARMABEES",
        "yf_symbol": "^CNXPHARMA",
    },
    "FMCG": {
        "sector": "FMCG",
        "index_name": "Nifty FMCG",
        "tv_ticker": "NSE:FMCGIETF",
        "yf_symbol": "^CNXFMCG",
    },
    "Metals": {
        "sector": "Metals",
        "index_name": "Nifty Metal",
        "tv_ticker": "NSE:METALIETF",
        "yf_symbol": "^CNXMETAL",
    },
    "Energy": {
        "sector": "Energy",
        "index_name": "Nifty Energy",
        "tv_ticker": "NSE:CNXENERGY",
        "yf_symbol": "^CNXENERGY",
    },
    "Capital Goods": {
        "sector": "Capital Goods",
        "index_name": "Nifty Infra & CapGoods",
        "tv_ticker": "NSE:INFRABEES",
        "yf_symbol": "^CNXINFRA",
    },
}

MARKET_BENCHMARK_TICKERS = {
    "NIFTY_50": "NSE:NIFTY",
    "NIFTY_500": "NSE:CNX500",
}

# Explicit lookup for well-known Indian equities so sector categorization is 100% institutional-grade
KNOWN_SYMBOL_SECTOR_MAP: Dict[str, str] = {
    "HDFCBANK": "Banking",
    "ICICIBANK": "Banking",
    "SBIN": "Banking",
    "AXISBANK": "Banking",
    "KOTAKBANK": "Banking",
    "INDUSINDBK": "Banking",
    "BANKBARODA": "Banking",
    "PNB": "Banking",
    "FEDERALBNK": "Banking",
    "IDFCFIRSTB": "Banking",
    "AUBANK": "Banking",
    "BANDHANBNK": "Banking",
    "CANBK": "Banking",
    "UNIONBANK": "Banking",
    "BAJFINANCE": "Financial Services",
    "BAJAJFINSV": "Financial Services",
    "JIOFIN": "Financial Services",
    "CHOLAFIN": "Financial Services",
    "SHRIRAMFIN": "Financial Services",
    "PFC": "Financial Services",
    "RECLTD": "Financial Services",
    "HDFCLIFE": "Financial Services",
    "SBILIFE": "Financial Services",
    "ICICIPRULI": "Financial Services",
    "MUTHOOTFIN": "Financial Services",
    "TCS": "IT",
    "INFY": "IT",
    "HCLTECH": "IT",
    "WIPRO": "IT",
    "TECHM": "IT",
    "LTIM": "IT",
    "PERSISTENT": "IT",
    "COFORGE": "IT",
    "MPHASIS": "IT",
    "KPITTECH": "IT",
    "TATAELXSI": "IT",
    "MARUTI": "Automobile",
    "TATAMOTORS": "Automobile",
    "M&M": "Automobile",
    "BAJAJ-AUTO": "Automobile",
    "EICHERMOT": "Automobile",
    "HEROMOTOCO": "Automobile",
    "TVSMOTOR": "Automobile",
    "ASHOKLEY": "Automobile",
    "BHARATFORG": "Automobile",
    "MOTHERSON": "Automobile",
    "SUNPHARMA": "Pharma",
    "CIPLA": "Pharma",
    "DRREDDY": "Pharma",
    "DIVISLAB": "Pharma",
    "APOLLOHOSP": "Pharma",
    "LUPIN": "Pharma",
    "AUROPHARMA": "Pharma",
    "BIOCON": "Pharma",
    "TORNTPHARM": "Pharma",
    "ZYDUSLIFE": "Pharma",
    "ITC": "FMCG",
    "HINDUNILVR": "FMCG",
    "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG",
    "TATACONSUM": "FMCG",
    "GODREJCP": "FMCG",
    "DABUR": "FMCG",
    "MARICO": "FMCG",
    "VBL": "FMCG",
    "COLPAL": "FMCG",
    "TITAN": "FMCG",
    "TRENT": "FMCG",
    "TATASTEEL": "Metals",
    "JSWSTEEL": "Metals",
    "HINDALCO": "Metals",
    "VEDL": "Metals",
    "COALINDIA": "Metals",
    "NMDC": "Metals",
    "SAIL": "Metals",
    "JINDALSTEL": "Metals",
    "NATIONALUM": "Metals",
    "RELIANCE": "Energy",
    "ONGC": "Energy",
    "NTPC": "Energy",
    "POWERGRID": "Energy",
    "BPCL": "Energy",
    "IOC": "Energy",
    "GAIL": "Energy",
    "TATAPOWER": "Energy",
    "ADANIGREEN": "Energy",
    "ADANIENSOL": "Energy",
    "LT": "Capital Goods",
    "HAL": "Capital Goods",
    "BEL": "Capital Goods",
    "SIEMENS": "Capital Goods",
    "ABB": "Capital Goods",
    "BHEL": "Capital Goods",
    "CGPOWER": "Capital Goods",
    "CUMMINSIND": "Capital Goods",
    "ADANIPORTS": "Capital Goods",
    "ADANIENT": "Capital Goods",
    "ULTRACEMCO": "Capital Goods",
    "GRASIM": "Capital Goods",
    "DLF": "Capital Goods",
}


def _classify_canonical_sector(symbol: str, raw_sector: Optional[str], raw_industry: Optional[str], name: Optional[str] = None) -> str:
    """
    Maps any NSE/BSE equity into its canonical Indian institutional sector bucket:
    Banking, Financial Services, IT, Automobile, Pharma, FMCG, Metals, Energy, or Capital Goods.
    """
    sym_up = (symbol or "").strip().upper()
    if sym_up in KNOWN_SYMBOL_SECTOR_MAP:
        return KNOWN_SYMBOL_SECTOR_MAP[sym_up]

    sec_l = (raw_sector or "").lower()
    ind_l = (raw_industry or "").lower()
    nm_l = (name or "").lower()
    combined = f"{sec_l} {ind_l} {nm_l}"

    if "bank" in ind_l or "bank" in nm_l:
        return "Banking"
    if "finance" in sec_l or any(k in combined for k in ["insurance", "finserv", "lending", "credit", "investment", "broking", "capital market", "nbfc", "housing fin"]):
        return "Financial Services"
    if any(k in combined for k in ["technology", "software", "it service", "computer", "internet", "digital", "saas"]):
        return "IT"
    if any(k in combined for k in ["motor", "auto", "vehicle", "tire", "tyre", "two wheeler", "tractor"]):
        return "Automobile"
    if any(k in combined for k in ["health", "pharma", "drug", "hospital", "biotech", "medical", "diagnostic", "life science"]):
        return "Pharma"
    if any(k in combined for k in ["consumer", "food", "beverage", "tobacco", "household", "personal", "fmcg", "apparel", "retail", "jewel"]):
        return "FMCG"
    if any(k in combined for k in ["steel", "metal", "mining", "aluminum", "aluminium", "copper", "zinc", "iron", "mineral"]):
        return "Metals"
    if any(k in combined for k in ["energy", "oil", "gas", "petrol", "refin", "power", "electric", "utility", "utilities", "solar", "coal"]):
        return "Energy"
    if any(k in combined for k in ["industrial", "engineering", "construction", "infra", "cement", "defence", "defense", "aerospace", "machinery", "electrical", "capital", "real estate", "realty", "logistics", "port"]):
        return "Capital Goods"

    return "Capital Goods"


# ----------------- REQUEST SCHEMAS ----------------- #
class WatchlistCreateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    initial_stocks: Optional[List[Dict[str, Any]]] = None


class WatchlistUpdateReq(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class WatchlistAddStockReq(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=40)
    exchange: str = Field("NSE", max_length=15)
    company_name: Optional[str] = None
    sector: Optional[str] = None


class WatchlistMoveStockReq(BaseModel):
    target_watchlist_id: int
    keep_copy: bool = False


class WatchlistReorderReq(BaseModel):
    ordered_item_ids: List[int]


# ----------------- MULTI-TIMEFRAME MARKET DATA BATCH ENGINE ----------------- #
def _fetch_batch_quotes_and_benchmarks(stock_tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetches live / official close quotes AND 7-timeframe returns (1D, 1W, 1M, 3M, 6M, YTD, 1Y)
    for all requested stocks + Nifty 50 + Nifty 500 + all Sectoral Benchmarks in a SINGLE HTTP call.
    Caches results in memory so server CPU/network overhead stays near zero.
    """
    benchmark_tickers = list(MARKET_BENCHMARK_TICKERS.values()) + [
        b["tv_ticker"] for b in SECTOR_BENCHMARKS.values()
    ]
    all_tickers = list(set(stock_tickers + benchmark_tickers))
    if not all_tickers:
        return {}

    now_ts = time_mod.time()
    ttl = 12.0 if ScreenerEngine.is_market_open() else 180.0

    missing_tickers = [
        t for t in all_tickers
        if t not in _QUOTE_CACHE or (now_ts - _QUOTE_CACHE_TS.get(t, 0.0)) > ttl
    ]

    if missing_tickers:
        try:
            resp = requests.post(
                "https://scanner.tradingview.com/india/scan",
                json={
                    "symbols": {"tickers": missing_tickers, "query": {"types": []}},
                    "columns": [
                        "name",
                        "description",
                        "close",
                        "change",
                        "change_abs",
                        "volume",
                        "price_52_week_high",
                        "price_52_week_low",
                        "sector",
                        "industry",
                        "Perf.W",
                        "Perf.1M",
                        "Perf.3M",
                        "Perf.6M",
                        "Perf.YTD",
                        "Perf.Y",
                        "SMA20",
                        "EMA50",
                        "SMA200",
                        "RSI",
                        "high",
                        "low",
                        "open",
                    ],
                },
                timeout=6,
            )
            if resp.status_code == 200:
                rows = resp.json().get("data", [])
                for row in rows:
                    s_full = row.get("s", "")
                    d = row.get("d", [])
                    if not s_full or len(d) < 16:
                        continue
                    exch, sym = s_full.split(":", 1) if ":" in s_full else ("NSE", s_full)
                    ltp = round(float(d[2] or 0.0), 2)
                    chg_1d = round(float(d[3] or 0.0), 2)
                    chg_abs = round(float(d[4] or 0.0), 2)
                    vol = int(d[5] or 0)
                    high_52w = round(float(d[6] or ltp or 0.0), 2)
                    low_52w = round(float(d[7] or ltp or 0.0), 2)
                    raw_sector = d[8]
                    raw_industry = d[9]
                    comp_name = d[1] or sym

                    perf_map = {
                        "1D": chg_1d,
                        "1W": round(float(d[10] if d[10] is not None else chg_1d), 2),
                        "1M": round(float(d[11] if d[11] is not None else chg_1d), 2),
                        "3M": round(float(d[12] if d[12] is not None else chg_1d), 2),
                        "6M": round(float(d[13] if d[13] is not None else chg_1d), 2),
                        "YTD": round(float(d[14] if d[14] is not None else chg_1d), 2),
                        "1Y": round(float(d[15] if d[15] is not None else chg_1d), 2),
                    }

                    sma20 = round(float(d[16]), 2) if len(d) > 16 and d[16] else None
                    ema50 = round(float(d[17]), 2) if len(d) > 17 and d[17] else None
                    sma200 = round(float(d[18]), 2) if len(d) > 18 and d[18] else None
                    rsi = round(float(d[19]), 1) if len(d) > 19 and d[19] is not None else 50.0
                    day_high = round(float(d[20] or ltp), 2) if len(d) > 20 and d[20] else ltp
                    day_low = round(float(d[21] or ltp), 2) if len(d) > 21 and d[21] else ltp
                    day_open = round(float(d[22] or (ltp - chg_abs)), 2) if len(d) > 22 and d[22] else round(ltp - chg_abs, 2)

                    canonical_sec = _classify_canonical_sector(sym, raw_sector, raw_industry, comp_name)

                    _QUOTE_CACHE[s_full] = {
                        "ticker": s_full,
                        "symbol": d[0] or sym,
                        "exchange": exch,
                        "name": comp_name,
                        "ltp": ltp,
                        "change": chg_abs,
                        "change_pct": chg_1d,
                        "perf": perf_map,
                        "volume": vol,
                        "high_52w": high_52w,
                        "low_52w": low_52w,
                        "sector": canonical_sec,
                        "raw_industry": raw_industry or canonical_sec,
                        "sma20": sma20,
                        "ema50": ema50,
                        "sma200": sma200,
                        "rsi": rsi,
                        "day_high": day_high,
                        "day_low": day_low,
                        "day_open": day_open,
                        "prev_close": round(ltp - chg_abs, 2),
                    }
                    _QUOTE_CACHE_TS[s_full] = now_ts
        except Exception as e:
            logger.warning(f"Watchlist batch quote fetch error: {e}")

    # Overlay live Dhan quotes if present in ScreenerEngine
    dhan_quotes = getattr(ScreenerEngine, "_last_eq_quotes", {}) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for t in all_tickers:
        exch, sym = t.split(":", 1) if ":" in t else ("NSE", t)
        base = dict(_QUOTE_CACHE.get(t, {}))
        if not base:
            continue
        perf_copy = dict(base.get("perf") or {})
        if sym in dhan_quotes and dhan_quotes[sym] > 0:
            live_p = round(float(dhan_quotes[sym]), 2)
            prev_c = base.get("prev_close") or base.get("ltp") or live_p
            base["ltp"] = live_p
            if prev_c and prev_c > 0:
                base["change"] = round(live_p - prev_c, 2)
                new_1d = round(((live_p - prev_c) / prev_c) * 100.0, 2)
                base["change_pct"] = new_1d
                perf_copy["1D"] = new_1d
        base["perf"] = perf_copy
        out[t] = base
    return out


def _generate_market_intelligence(
    stocks: List[Dict[str, Any]],
    sectors_summary: List[Dict[str, Any]],
    nifty50_perf: Dict[str, float],
) -> Dict[str, List[str]]:
    """
    Generates concise, factual, data-driven institutional insights per timeframe (1D..1Y)
    from live stock, sector, and Nifty 50 relative performance.
    """
    insights_by_tf: Dict[str, List[str]] = {}

    for tf in TIMEFRAME_KEYS:
        notes: List[str] = []
        n50_ret = nifty50_perf.get(tf, 0.0)

        if not stocks:
            insights_by_tf[tf] = ["Add NSE or BSE stocks to generate live sector and relative strength intelligence."]
            continue

        # 1. Count dual outperformers (beating both their sector and Nifty 50)
        dual_outperformers = [
            s for s in stocks
            if (s.get("rel_vs_sector", {}).get(tf) or 0.0) > 0
            and (s.get("rel_vs_nifty50", {}).get(tf) or 0.0) > 0
        ]
        if dual_outperformers:
            count_d = len(dual_outperformers)
            word = "stock is" if count_d == 1 else "stocks are"
            top_sym = max(dual_outperformers, key=lambda x: x["rel_vs_nifty50"].get(tf, 0.0))["symbol"]
            notes.append(
                f"{count_d} of your {len(stocks)} tracked {word} outperforming both their sector index and Nifty 50 ({tf}), led by {top_sym}."
            )

        # 2. Best / worst sector vs Nifty 50
        if sectors_summary:
            sorted_secs = sorted(
                sectors_summary,
                key=lambda s: s.get("sector_vs_nifty50", {}).get(tf, 0.0),
                reverse=True,
            )
            top_sec = sorted_secs[0]
            top_alpha = top_sec.get("sector_vs_nifty50", {}).get(tf, 0.0)
            if top_alpha > 0.05:
                notes.append(
                    f"{top_sec['sector']} ({top_sec['index_name']}) is outperforming Nifty 50 by +{top_alpha:.2f} percentage points ({tf})."
                )
            elif top_alpha < -0.05:
                notes.append(
                    f"{top_sec['sector']} ({top_sec['index_name']}) is trailing Nifty 50 by {top_alpha:.2f} percentage points ({tf})."
                )

            if len(sorted_secs) > 1:
                lag_sec = sorted_secs[-1]
                lag_alpha = lag_sec.get("sector_vs_nifty50", {}).get(tf, 0.0)
                if lag_alpha < -0.1:
                    notes.append(
                        f"{lag_sec['sector']} stocks are underperforming Nifty 50 ({lag_sec['index_name']} {lag_alpha:+.2f} pts vs market)."
                    )

        # 3. Sector breadth insight for largest sector group in user's watchlist
        if sectors_summary:
            largest_sec = max(sectors_summary, key=lambda s: s.get("stock_count", 0))
            if largest_sec["stock_count"] >= 2:
                pos_rs_count = sum(
                    1 for st in largest_sec.get("stocks", [])
                    if (st.get("rel_vs_sector", {}).get(tf) or 0.0) > 0
                )
                notes.append(
                    f"{pos_rs_count} of your {largest_sec['stock_count']} {largest_sec['sector']} stocks are showing positive relative strength against {largest_sec['index_name']} ({tf})."
                )

        if not notes:
            notes.append(f"Nifty 50 reference change is {n50_ret:+.2f}% over the {tf} timeframe.")

        insights_by_tf[tf] = notes[:4]

    return insights_by_tf


def _serialize_user_watchlists(db: Session, user: User) -> Dict[str, Any]:
    """
    Builds the complete response for the authenticated user's watchlists:
    - If the user has not created any watchlist yet, returns `needs_onboarding: True`
      so the UI can guide them through naming and creating their first personalised watchlist.
    - Enriches every stock with 7-timeframe returns (1D, 1W, 1M, 3M, 6M, YTD, 1Y),
      Sector Index performance, Nifty 50 performance, Nifty 500 performance,
      Relative Strength vs Sector, and Relative Strength vs Market.
    """
    lists = (
        db.query(Watchlist)
        .filter(Watchlist.user_id == user.id)
        .order_by(Watchlist.display_order.asc(), Watchlist.id.asc())
        .all()
    )

    if not lists:
        # Still fetch benchmark indices so onboarding shows live market context
        quote_map = _fetch_batch_quotes_and_benchmarks([])
        n50_q = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_50"], {})
        n500_q = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_500"], {})
        return {
            "status": "success",
            "user": user.username,
            "needs_onboarding": True,
            "market_open": ScreenerEngine.is_market_open(),
            "last_updated": ScreenerEngine.get_session_timestamp_str(),
            "benchmarks": {
                "nifty50": {
                    "name": "Nifty 50",
                    "ltp": n50_q.get("ltp"),
                    "perf": n50_q.get("perf", {k: 0.0 for k in TIMEFRAME_KEYS}),
                },
                "nifty500": {
                    "name": "Nifty 500",
                    "ltp": n500_q.get("ltp"),
                    "perf": n500_q.get("perf", {k: 0.0 for k in TIMEFRAME_KEYS}),
                },
            },
            "watchlists": [],
        }

    wl_ids = [w.id for w in lists]
    all_items = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.user_id == user.id, WatchlistStock.watchlist_id.in_(wl_ids))
        .order_by(WatchlistStock.display_order.asc(), WatchlistStock.id.asc())
        .all()
    )

    stock_tickers = [f"{(it.exchange or 'NSE').upper()}:{it.stock_symbol.upper()}" for it in all_items]
    quote_map = _fetch_batch_quotes_and_benchmarks(stock_tickers)

    n50_q = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_50"], {})
    n500_q = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_500"], {})
    n50_perf: Dict[str, float] = n50_q.get("perf") or {k: 0.0 for k in TIMEFRAME_KEYS}
    n500_perf: Dict[str, float] = n500_q.get("perf") or {k: 0.0 for k in TIMEFRAME_KEYS}

    # Build sector benchmark performance lookup
    sector_bench_data: Dict[str, Dict[str, Any]] = {}
    for sec_name, meta in SECTOR_BENCHMARKS.items():
        sq = quote_map.get(meta["tv_ticker"], {})
        s_perf = sq.get("perf") or dict(n50_perf)
        sec_vs_n50 = {
            tf: round(float(s_perf.get(tf, 0.0)) - float(n50_perf.get(tf, 0.0)), 2)
            for tf in TIMEFRAME_KEYS
        }
        sector_bench_data[sec_name] = {
            "sector": sec_name,
            "index_name": meta["index_name"],
            "tv_ticker": meta["tv_ticker"],
            "ltp": sq.get("ltp"),
            "perf": s_perf,
            "vs_nifty50": sec_vs_n50,
        }

    items_by_wl: Dict[int, List[Dict[str, Any]]] = {w.id: [] for w in lists}
    for it in all_items:
        exch = (it.exchange or "NSE").upper()
        sym = it.stock_symbol.upper()
        t_key = f"{exch}:{sym}"
        q = quote_map.get(t_key, {})

        ltp = q.get("ltp")
        chg = q.get("change")
        chg_pct = q.get("change_pct")

        canonical_sec = _classify_canonical_sector(
            sym,
            q.get("sector") or it.sector,
            q.get("raw_industry"),
            q.get("name") or it.company_name,
        )
        sec_bench = sector_bench_data.get(canonical_sec) or sector_bench_data["Capital Goods"]
        sec_perf = sec_bench["perf"]
        stk_perf = q.get("perf") or {k: (chg_pct or 0.0) for k in TIMEFRAME_KEYS}

        rel_vs_sector = {
            tf: round(float(stk_perf.get(tf, 0.0)) - float(sec_perf.get(tf, 0.0)), 2)
            for tf in TIMEFRAME_KEYS
        }
        rel_vs_nifty50 = {
            tf: round(float(stk_perf.get(tf, 0.0)) - float(n50_perf.get(tf, 0.0)), 2)
            for tf in TIMEFRAME_KEYS
        }
        rel_vs_nifty500 = {
            tf: round(float(stk_perf.get(tf, 0.0)) - float(n500_perf.get(tf, 0.0)), 2)
            for tf in TIMEFRAME_KEYS
        }

        items_by_wl.setdefault(it.watchlist_id, []).append(
            {
                "id": it.id,
                "watchlist_id": it.watchlist_id,
                "symbol": sym,
                "exchange": exch,
                "name": q.get("name") or it.company_name or sym,
                "sector": canonical_sec,
                "sector_index_name": sec_bench["index_name"],
                "ltp": ltp if ltp and ltp > 0 else None,
                "change": chg if ltp and ltp > 0 else None,
                "change_pct": chg_pct if ltp and ltp > 0 else None,
                "perf": stk_perf,
                "sector_perf": sec_perf,
                "nifty50_perf": n50_perf,
                "nifty500_perf": n500_perf,
                "rel_vs_sector": rel_vs_sector,
                "rel_vs_nifty50": rel_vs_nifty50,
                "rel_vs_nifty500": rel_vs_nifty500,
                "volume": q.get("volume"),
                "high_52w": q.get("high_52w"),
                "low_52w": q.get("low_52w"),
                "day_high": q.get("day_high"),
                "day_low": q.get("day_low"),
                "day_open": q.get("day_open"),
                "prev_close": q.get("prev_close"),
                "sma20": q.get("sma20"),
                "ema50": q.get("ema50"),
                "sma200": q.get("sma200"),
                "rsi": q.get("rsi"),
                "display_order": it.display_order,
                "added_at": it.added_at.isoformat() if it.added_at else None,
            }
        )

    serialized_lists = []
    for w in lists:
        stk_list = items_by_wl.get(w.id, [])

        # Overall watchlist stats per timeframe
        perf_by_tf: Dict[str, Dict[str, Any]] = {}
        for tf in TIMEFRAME_KEYS:
            vals = [float(s["perf"].get(tf, 0.0)) for s in stk_list if s.get("ltp")]
            adv = sum(1 for v in vals if v > 0)
            dec = sum(1 for v in vals if v < 0)
            avg_v = round(sum(vals) / len(vals), 2) if vals else 0.0
            perf_by_tf[tf] = {
                "avg_return": avg_v,
                "advances": adv,
                "declines": dec,
                "vs_nifty50": round(avg_v - float(n50_perf.get(tf, 0.0)), 2),
                "vs_nifty500": round(avg_v - float(n500_perf.get(tf, 0.0)), 2),
            }

        # Group stocks by canonical sector
        sec_groups_map: Dict[str, List[Dict[str, Any]]] = {}
        for s in stk_list:
            sec_groups_map.setdefault(s["sector"], []).append(s)

        sectors_summary = []
        for sec_name, sec_stocks in sec_groups_map.items():
            s_bench = sector_bench_data.get(sec_name) or sector_bench_data["Capital Goods"]
            avg_tracked_perf: Dict[str, float] = {}
            adv_by_tf: Dict[str, int] = {}
            dec_by_tf: Dict[str, int] = {}
            for tf in TIMEFRAME_KEYS:
                s_vals = [float(st["perf"].get(tf, 0.0)) for st in sec_stocks]
                avg_tracked_perf[tf] = round(sum(s_vals) / len(s_vals), 2) if s_vals else 0.0
                adv_by_tf[tf] = sum(1 for v in s_vals if v > 0)
                dec_by_tf[tf] = sum(1 for v in s_vals if v < 0)

            sectors_summary.append(
                {
                    "sector": sec_name,
                    "index_name": s_bench["index_name"],
                    "index_ltp": s_bench["ltp"],
                    "stock_count": len(sec_stocks),
                    "sector_index_perf": s_bench["perf"],
                    "sector_vs_nifty50": s_bench["vs_nifty50"],
                    "tracked_avg_perf": avg_tracked_perf,
                    "advances_by_tf": adv_by_tf,
                    "declines_by_tf": dec_by_tf,
                    "stocks": sec_stocks,
                }
            )

        sectors_summary.sort(key=lambda x: x["stock_count"], reverse=True)
        intelligence = _generate_market_intelligence(stk_list, sectors_summary, n50_perf)

        d1_stats = perf_by_tf["1D"]
        serialized_lists.append(
            {
                "id": w.id,
                "name": w.name,
                "display_order": w.display_order,
                "stock_count": len(stk_list),
                "avg_change_pct": d1_stats["avg_return"],
                "advances": d1_stats["advances"],
                "declines": d1_stats["declines"],
                "performance_by_tf": perf_by_tf,
                "sectors": sectors_summary,
                "intelligence": intelligence,
                "created_at": w.created_at.isoformat() if w.created_at else None,
                "updated_at": w.updated_at.isoformat() if w.updated_at else None,
                "stocks": stk_list,
            }
        )

    return {
        "status": "success",
        "user": user.username,
        "needs_onboarding": False,
        "market_open": ScreenerEngine.is_market_open(),
        "last_updated": ScreenerEngine.get_session_timestamp_str(),
        "benchmarks": {
            "nifty50": {
                "name": "Nifty 50",
                "ltp": n50_q.get("ltp"),
                "perf": n50_perf,
            },
            "nifty500": {
                "name": "Nifty 500",
                "ltp": n500_q.get("ltp"),
                "perf": n500_perf,
            },
            "sectors": sector_bench_data,
        },
        "watchlists": serialized_lists,
    }


# ----------------- API ENDPOINTS (STRICT USER OWNERSHIP) ----------------- #

@router.get("")
def list_user_watchlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_user_watchlists(db, current_user)


@router.post("")
def create_watchlist(
    req: WatchlistCreateReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Watchlist name cannot be empty")

    count = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).count()
    if count >= 25:
        raise HTTPException(status_code=400, detail="Maximum limit of 25 watchlists reached")

    wl = Watchlist(
        user_id=current_user.id,
        name=clean_name,
        display_order=count,
    )
    db.add(wl)
    db.commit()
    db.refresh(wl)

    if req.initial_stocks:
        seen = set()
        order_idx = 0
        for item in req.initial_stocks[:50]:
            sym = (item.get("symbol") or "").strip().upper()
            exch = (item.get("exchange") or "NSE").strip().upper()
            if not sym or (sym, exch) in seen:
                continue
            seen.add((sym, exch))
            db.add(
                WatchlistStock(
                    watchlist_id=wl.id,
                    user_id=current_user.id,
                    stock_symbol=sym,
                    company_name=item.get("name") or item.get("company_name") or sym,
                    exchange=exch if exch in ("NSE", "BSE") else "NSE",
                    sector=item.get("sector") or _classify_canonical_sector(sym, None, None, item.get("name")),
                    display_order=order_idx,
                )
            )
            order_idx += 1
        db.commit()

    return {
        "status": "created",
        "watchlist_id": wl.id,
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.put("/{watchlist_id}")
def rename_watchlist(
    watchlist_id: int,
    req: WatchlistUpdateReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wl = (
        db.query(Watchlist)
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Watchlist name cannot be empty")

    wl.name = clean_name
    wl.updated_at = datetime.utcnow()
    db.commit()
    return {
        "status": "updated",
        "watchlist_id": wl.id,
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.post("/{watchlist_id}/duplicate")
def duplicate_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = (
        db.query(Watchlist)
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    count = db.query(Watchlist).filter(Watchlist.user_id == current_user.id).count()
    new_wl = Watchlist(
        user_id=current_user.id,
        name=f"{source.name} Copy",
        display_order=count,
    )
    db.add(new_wl)
    db.commit()
    db.refresh(new_wl)

    source_stocks = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == source.id, WatchlistStock.user_id == current_user.id)
        .order_by(WatchlistStock.display_order.asc(), WatchlistStock.id.asc())
        .all()
    )
    for idx, st in enumerate(source_stocks):
        db.add(
            WatchlistStock(
                watchlist_id=new_wl.id,
                user_id=current_user.id,
                stock_symbol=st.stock_symbol,
                company_name=st.company_name,
                exchange=st.exchange,
                sector=st.sector,
                display_order=idx,
            )
        )
    db.commit()
    return {
        "status": "duplicated",
        "watchlist_id": new_wl.id,
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.delete("/{watchlist_id}")
def delete_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wl = (
        db.query(Watchlist)
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    db.query(WatchlistStock).filter(
        WatchlistStock.watchlist_id == wl.id,
        WatchlistStock.user_id == current_user.id,
    ).delete()
    db.delete(wl)
    db.commit()

    return {
        "status": "deleted",
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.post("/{watchlist_id}/stocks")
def add_stock_to_watchlist(
    watchlist_id: int,
    req: WatchlistAddStockReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wl = (
        db.query(Watchlist)
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    sym = req.symbol.strip().upper()
    exch = (req.exchange or "NSE").strip().upper()
    if exch not in ("NSE", "BSE"):
        exch = "NSE"

    existing = (
        db.query(WatchlistStock)
        .filter(
            WatchlistStock.watchlist_id == wl.id,
            WatchlistStock.user_id == current_user.id,
            WatchlistStock.stock_symbol == sym,
            WatchlistStock.exchange == exch,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"{sym} ({exch}) is already in {wl.name}")

    current_count = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == wl.id, WatchlistStock.user_id == current_user.id)
        .count()
    )

    canonical_sec = _classify_canonical_sector(sym, req.sector, None, req.company_name)
    new_item = WatchlistStock(
        watchlist_id=wl.id,
        user_id=current_user.id,
        stock_symbol=sym,
        company_name=req.company_name or sym,
        exchange=exch,
        sector=canonical_sec,
        display_order=current_count,
    )
    db.add(new_item)
    wl.updated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "added",
        "added_symbol": sym,
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.delete("/{watchlist_id}/stocks/{item_id}")
def remove_stock_from_watchlist(
    watchlist_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WatchlistStock)
        .filter(
            WatchlistStock.id == item_id,
            WatchlistStock.watchlist_id == watchlist_id,
            WatchlistStock.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Stock not found in watchlist")

    removed_symbol = item.stock_symbol
    db.delete(item)
    db.commit()

    return {
        "status": "removed",
        "removed_symbol": removed_symbol,
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.post("/{watchlist_id}/stocks/{item_id}/move")
def move_stock_between_watchlists(
    watchlist_id: int,
    item_id: int,
    req: WatchlistMoveStockReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = (
        db.query(WatchlistStock)
        .filter(
            WatchlistStock.id == item_id,
            WatchlistStock.watchlist_id == watchlist_id,
            WatchlistStock.user_id == current_user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Stock not found in source watchlist")

    target_wl = (
        db.query(Watchlist)
        .filter(Watchlist.id == req.target_watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not target_wl:
        raise HTTPException(status_code=404, detail="Target watchlist not found")

    dup = (
        db.query(WatchlistStock)
        .filter(
            WatchlistStock.watchlist_id == target_wl.id,
            WatchlistStock.user_id == current_user.id,
            WatchlistStock.stock_symbol == item.stock_symbol,
            WatchlistStock.exchange == item.exchange,
        )
        .first()
    )
    if not dup:
        target_count = (
            db.query(WatchlistStock)
            .filter(WatchlistStock.watchlist_id == target_wl.id, WatchlistStock.user_id == current_user.id)
            .count()
        )
        if req.keep_copy:
            db.add(
                WatchlistStock(
                    watchlist_id=target_wl.id,
                    user_id=current_user.id,
                    stock_symbol=item.stock_symbol,
                    company_name=item.company_name,
                    exchange=item.exchange,
                    sector=item.sector,
                    display_order=target_count,
                )
            )
        else:
            item.watchlist_id = target_wl.id
            item.display_order = target_count
    elif not req.keep_copy:
        db.delete(item)

    db.commit()
    return {
        "status": "moved",
        "data": _serialize_user_watchlists(db, current_user),
    }


@router.put("/{watchlist_id}/reorder")
def reorder_watchlist_stocks(
    watchlist_id: int,
    req: WatchlistReorderReq,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wl = (
        db.query(Watchlist)
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    items = (
        db.query(WatchlistStock)
        .filter(WatchlistStock.watchlist_id == wl.id, WatchlistStock.user_id == current_user.id)
        .all()
    )
    item_map = {it.id: it for it in items}
    for order_idx, item_id in enumerate(req.ordered_item_ids):
        if item_id in item_map:
            item_map[item_id].display_order = order_idx
    db.commit()

    return {
        "status": "reordered",
        "data": _serialize_user_watchlists(db, current_user),
    }


# ----------------- INTELLIGENT NSE / BSE STOCK SEARCH ----------------- #
@router.get("/search")
def search_indian_stocks(
    q: str = Query("", description="Company name or NSE/BSE ticker"),
    exchange: str = Query("ALL", description="ALL, NSE, or BSE"),
    current_user: User = Depends(get_current_user),
):
    query_str = (q or "").strip()
    exch_filter = (exchange or "ALL").strip().upper()

    if not query_str:
        default_tickers = [f"NSE:{s['symbol']}" for s in NIFTY_50_STOCKS[:16]]
        quotes = _fetch_batch_quotes_and_benchmarks(default_tickers)
        results = [quotes[t] for t in default_tickers if t in quotes and quotes[t].get("ltp")]
        return {"status": "success", "results": results}

    cache_key = f"{exch_filter}:{query_str.lower()}"
    now_ts = time_mod.time()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and (now_ts - cached["ts"] < 30.0):
        return {"status": "success", "results": cached["results"]}

    filters = [
        {"left": "typespecs", "operation": "has", "right": ["common"]},
    ]
    if exch_filter in ("NSE", "BSE"):
        filters.append({"left": "exchange", "operation": "equal", "right": exch_filter})
    else:
        filters.append({"left": "exchange", "operation": "in_range", "right": ["NSE", "BSE"]})

    results = []
    try:
        tv_resp = requests.post(
            "https://scanner.tradingview.com/india/scan",
            json={
                "filter": filters,
                "filter2": {
                    "operator": "or",
                    "operands": [
                        {"operation": {"operator": "and", "operands": [{"expression": {"left": "name", "operation": "match", "right": query_str}}]}},
                        {"operation": {"operator": "and", "operands": [{"expression": {"left": "description", "operation": "match", "right": query_str}}]}},
                    ],
                },
                "markets": ["india"],
                "columns": [
                    "name",
                    "description",
                    "close",
                    "change",
                    "change_abs",
                    "volume",
                    "price_52_week_high",
                    "price_52_week_low",
                    "sector",
                    "industry",
                    "exchange",
                ],
                "sort": {"sortBy": "volume", "sortOrder": "desc"},
                "range": [0, 24],
            },
            timeout=6,
        )
        if tv_resp.status_code == 200:
            for row in tv_resp.json().get("data", []):
                s_full = row.get("s", "")
                d = row.get("d", [])
                if not s_full or len(d) < 11:
                    continue
                ltp = round(float(d[2] or 0.0), 2)
                if ltp <= 0:
                    continue
                sym = d[0]
                comp_name = d[1] or sym
                canonical_sec = _classify_canonical_sector(sym, d[8], d[9], comp_name)
                results.append(
                    {
                        "ticker": s_full,
                        "symbol": sym,
                        "name": comp_name,
                        "ltp": ltp,
                        "change_pct": round(float(d[3] or 0.0), 2),
                        "change": round(float(d[4] or 0.0), 2),
                        "volume": int(d[5] or 0),
                        "high_52w": round(float(d[6] or ltp), 2),
                        "low_52w": round(float(d[7] or ltp), 2),
                        "sector": canonical_sec,
                        "exchange": d[10] or (s_full.split(":")[0] if ":" in s_full else "NSE"),
                    }
                )
    except Exception as e:
        logger.warning(f"Stock search error: {e}")

    q_up = query_str.upper()
    results.sort(
        key=lambda x: (
            0 if x["symbol"].upper() == q_up else 1 if x["symbol"].upper().startswith(q_up) else 2,
            0 if x["exchange"] == "NSE" else 1,
        )
    )

    _SEARCH_CACHE[cache_key] = {"ts": now_ts, "results": results[:20]}
    return {"status": "success", "results": results[:20]}


# ----------------- HISTORICAL CHART & BENCHMARK COMPARISON ENDPOINT ----------------- #
@router.get("/history")
def get_stock_chart_history(
    symbol: str = Query(..., description="Stock symbol e.g. HDFCBANK"),
    exchange: str = Query("NSE", description="NSE or BSE"),
    period: str = Query("1M", description="1D, 1W, 1M, 3M, 6M, YTD, 1Y, 5Y"),
    current_user: User = Depends(get_current_user),
):
    sym = symbol.strip().upper()
    exch = (exchange or "NSE").strip().upper()
    p_norm = (period or "1M").strip().upper()

    period_map = {
        "1D": ("1d", "5m"),
        "1W": ("5d", "15m"),
        "1M": ("1mo", "1d"),
        "3M": ("3mo", "1d"),
        "6M": ("6mo", "1d"),
        "YTD": ("ytd", "1d"),
        "1Y": ("1y", "1d"),
        "5Y": ("5y", "1wk"),
        "4H": ("60d", "1h"),
        "D": ("5y", "1d"),
        "W": ("10y", "1wk"),
    }
    yf_range, yf_interval = period_map.get(p_norm, ("1mo", "1d"))

    # Direct mapping for index tickers
    INDEX_TICKER_MAP = {
        "NIFTY": "^NSEI",
        "NIFTY_50": "^NSEI",
        "CNX500": "^CRSLDX",
        "NIFTY_500": "^CRSLDX",
        "BANKNIFTY": "^NSEBANK",
        "NIFTY_BANK": "^NSEBANK",
        "CNXFINANCE": "NIFTY_FIN_SERVICE.NS",
        "NIFTY_FIN_SERVICE": "NIFTY_FIN_SERVICE.NS",
        "CNXIT": "^CNXIT",
        "NIFTY_IT": "^CNXIT",
        "AUTOBEES": "^CNXAUTO",
        "NIFTY_AUTO": "^CNXAUTO",
        "PHARMABEES": "^CNXPHARMA",
        "NIFTY_PHARMA": "^CNXPHARMA",
        "FMCGIETF": "^CNXFMCG",
        "NIFTY_FMCG": "^CNXFMCG",
        "METALIETF": "^CNXMETAL",
        "NIFTY_METAL": "^CNXMETAL",
        "CNXENERGY": "^CNXENERGY",
        "NIFTY_ENERGY": "^CNXENERGY",
        "INFRABEES": "^CNXINFRA",
        "NIFTY_INFRA": "^CNXINFRA",
        "MOREALTY": "^CNXREALTY",
        "NIFTY_REALTY": "^CNXREALTY",
        "PSUBNKBEES": "^CNXPSUBANK",
        "NIFTY_PSU_BANK": "^CNXPSUBANK",
        "PVTBANIETF": "PVTBANIETF.NS",
        "NIFTY_PVT_BANK": "PVTBANIETF.NS",
        "CONSUMBEES": "^CNXCONSUM",
        "NIFTY_CONSUMPTION": "^CNXCONSUM",
        "CPSEETF": "^CNXPSE",
        "NIFTY_PSE": "^CNXPSE",
        "MODEFENCE": "MODEFENCE.NS",
        "NIFTY_DEFENCE": "MODEFENCE.NS",
        "OILIETF": "OILIETF.NS",
        "NIFTY_OIL_GAS": "OILIETF.NS",
        "HEALTHY": "HEALTHY.NS",
        "NIFTY_HEALTHCARE": "HEALTHY.NS",
        "JUNIORBEES": "^NSMIDCP",
        "CNXMIDCAP": "^NSEMDCP50",
        "NIFTY_MIDCAP": "^NSEMDCP50",
        "HDFCSML250": "HDFCSML250.NS",
        "MNC": "^CNXMNC",
        "NIFTY_MNC": "^CNXMNC",
        "EVINDIA": "EVINDIA.NS",
        "MAKEINDIA": "MAKEINDIA.NS",
        "COMMOIETF": "COMMOIETF.NS",
        "NIFTY_COMMODITIES": "COMMOIETF.NS",
        "NIFTY_MEDIA": "CONSUMBEES.NS",
    }

    CUSTOM_SECTOR_BASKETS = {
        "SEC_CHEMICALS": ["SOLARINDS.NS", "PIDILITIND.NS", "SRF.NS", "LINDEINDIA.NS", "COROMANDEL.NS"],
        "SEC_CEMENT": ["ULTRACEMCO.NS", "GRASIM.NS", "AMBUJACEM.NS", "SHREECEM.NS", "JKCEMENT.NS"],
        "SEC_CAPGOODS": ["BHEL.NS", "ABB.NS", "CGPOWER.NS", "CUMMINSIND.NS", "SIEMENS.NS"],
        "SEC_RETAIL": ["DMART.NS", "TRENT.NS", "NAUKRI.NS", "TITAN.NS"],
        "SEC_TELECOM": ["BHARTIARTL.NS", "INDUSTOWER.NS", "TATACOMM.NS", "IDEA.NS"],
        "SEC_AVIATION": ["ADANIPORTS.NS", "INDIGO.NS", "GMRAIRPORT.NS", "CONCOR.NS"],
        "SEC_INTECH": ["NAUKRI.NS", "IRCTC.NS", "AFFLE.NS", "ZOMATO.NS"],
        "SEC_TEXTILES": ["PAGEIND.NS", "KPRMILL.NS", "WELSPUNLIV.NS", "TRIDENT.NS"],
        "SEC_HOTELS": ["INDHOTEL.NS", "EIHOTEL.NS", "LEMONTREE.NS", "CHALET.NS"],
        "SEC_MEDIA": ["SUNTV.NS", "PVRINOX.NS", "ZEEL.NS", "PFOCUS.NS"],
        "SEC_LOGISTICS": ["CONCOR.NS", "BLUEDART.NS", "DELHIVERY.NS"],
        "SEC_QSR": ["JUBLFOOD.NS", "DEVYANI.NS", "WESTLIFE.NS"],
        "SEC_DIVERSIFIED": ["GODREJIND.NS", "ADANIENT.NS", "RELIANCE.NS"],
    }

    if sym in INDEX_TICKER_MAP:
        yf_ticker = INDEX_TICKER_MAP[sym]
    elif sym.startswith("^") or sym.endswith(".NS") or sym.endswith(".BO"):
        yf_ticker = sym
    else:
        yf_suffix = ".BO" if exch == "BSE" else ".NS"
        yf_ticker = f"{sym}{yf_suffix}"

    cache_key = f"{exch}:{sym}:{p_norm}"
    now_ts = time_mod.time()
    cached = _HISTORY_CACHE.get(cache_key)
    if cached and (now_ts - cached["ts"] < (15.0 if ScreenerEngine.is_market_open() else 60.0)):
        return cached["payload"]

    quote_map = _fetch_batch_quotes_and_benchmarks([f"{exch}:{sym}"])
    quote = quote_map.get(f"{exch}:{sym}", {})
    canonical_sec = quote.get("sector") or _classify_canonical_sector(sym, None, None, sym)
    sec_meta = SECTOR_BENCHMARKS.get(canonical_sec) or SECTOR_BENCHMARKS["Capital Goods"]
    sec_quote = quote_map.get(sec_meta["tv_ticker"], {})
    n50_quote = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_50"], {})
    n500_quote = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_500"], {})

    candles = []
    if sym in CUSTOM_SECTOR_BASKETS:
        try:
            from concurrent.futures import ThreadPoolExecutor
            import pytz
            ist = pytz.timezone("Asia/Kolkata")
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            def _fetch_one(tk):
                try:
                    rr = requests.get(
                        f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}",
                        params={"range": yf_range, "interval": yf_interval, "includePrePost": "false"},
                        headers=headers, timeout=5
                    )
                    if rr.status_code == 200:
                        rl = rr.json().get("chart", {}).get("result", [])
                        if rl:
                            r0 = rl[0]
                            ts_list = r0.get("timestamp", []) or []
                            ind = (r0.get("indicators", {}).get("quote", [{}]) or [{}])[0]
                            op, hi, lo, cl, vl = ind.get("open", []), ind.get("high", []), ind.get("low", []), ind.get("close", []), ind.get("volume", [])
                            pts = {}
                            base_c = None
                            for i, t in enumerate(ts_list):
                                c_v = cl[i] if i < len(cl) else None
                                if c_v is None or c_v <= 0:
                                    continue
                                if base_c is None:
                                    base_c = float(c_v)
                                o_v = float(op[i] or c_v) if i < len(op) else float(c_v)
                                h_v = float(hi[i] or c_v) if i < len(hi) else float(c_v)
                                l_v = float(lo[i] or c_v) if i < len(lo) else float(c_v)
                                v_v = int(vl[i] or 0) if i < len(vl) and vl[i] is not None else 0
                                pts[t] = (1000.0 * o_v / base_c, 1000.0 * h_v / base_c, 1000.0 * l_v / base_c, 1000.0 * float(c_v) / base_c, v_v)
                            return pts
                except Exception:
                    pass
                return {}
            b_tickers = CUSTOM_SECTOR_BASKETS[sym]
            with ThreadPoolExecutor(max_workers=5) as ex:
                maps = [m for m in ex.map(_fetch_one, b_tickers) if m]
            if maps:
                # Use timestamps from the most complete series
                ref_ts = sorted(max(maps, key=lambda x: len(x)).keys())
                for ts in ref_ts:
                    vals = [m[ts] for m in maps if ts in m]
                    if not vals:
                        continue
                    n_v = len(vals)
                    o_avg = round(sum(x[0] for x in vals) / n_v, 2)
                    h_avg = round(sum(x[1] for x in vals) / n_v, 2)
                    l_avg = round(sum(x[2] for x in vals) / n_v, 2)
                    c_avg = round(sum(x[3] for x in vals) / n_v, 2)
                    v_sum = sum(x[4] for x in vals)
                    dt = datetime.fromtimestamp(ts, ist)
                    lbl = dt.strftime("%I:%M %p") if p_norm == "1D" else dt.strftime("%d %b %I:%M %p") if p_norm == "1W" else dt.strftime("%b %Y") if p_norm == "5Y" else dt.strftime("%d %b %Y")
                    candles.append({
                        "timestamp": ts, "label": lbl,
                        "open": o_avg, "high": max(h_avg, o_avg, c_avg), "low": min(l_avg, o_avg, c_avg), "close": c_avg, "volume": v_sum
                    })
        except Exception as e:
            logger.warning(f"Custom sector basket fetch failed for {sym}: {e}")
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        r = requests.get(
            url,
            params={"range": yf_range, "interval": yf_interval, "includePrePost": "false"},
            headers=headers,
            timeout=6,
        ) if not candles else type("Dummy", (), {"status_code": 0})()
        if r.status_code == 200:
            res_list = r.json().get("chart", {}).get("result", [])
            if res_list:
                r0 = res_list[0]
                timestamps = r0.get("timestamp", []) or []
                ind = (r0.get("indicators", {}).get("quote", [{}]) or [{}])[0]
                opens = ind.get("open", []) or []
                highs = ind.get("high", []) or []
                lows = ind.get("low", []) or []
                closes = ind.get("close", []) or []
                vols = ind.get("volume", []) or []

                import pytz
                ist = pytz.timezone("Asia/Kolkata")
                for idx, ts in enumerate(timestamps):
                    c_val = closes[idx] if idx < len(closes) else None
                    if c_val is None:
                        continue
                    dt = datetime.fromtimestamp(ts, ist)
                    if p_norm == "1D":
                        lbl = dt.strftime("%I:%M %p")
                    elif p_norm == "1W":
                        lbl = dt.strftime("%d %b %I:%M %p")
                    elif p_norm == "5Y":
                        lbl = dt.strftime("%b %Y")
                    else:
                        lbl = dt.strftime("%d %b %Y")

                    candles.append(
                        {
                            "timestamp": ts,
                            "label": lbl,
                            "open": round(float(opens[idx] or c_val), 2),
                            "high": round(float(highs[idx] or c_val), 2),
                            "low": round(float(lows[idx] or c_val), 2),
                            "close": round(float(c_val), 2),
                            "volume": int(vols[idx] or 0) if idx < len(vols) and vols[idx] is not None else 0,
                        }
                    )
    except Exception as e:
        logger.warning(f"History fetch failed for {yf_ticker}: {e}")

    period_change = 0.0
    period_change_pct = 0.0
    if len(candles) >= 2:
        first_c = candles[0]["close"]
        last_c = candles[-1]["close"]
        if first_c > 0:
            period_change = round(last_c - first_c, 2)
            period_change_pct = round(((last_c - first_c) / first_c) * 100.0, 2)

    tf_Lookup = p_norm if p_norm in TIMEFRAME_KEYS else "1Y"
    stk_tf_ret = quote.get("perf", {}).get(tf_Lookup, period_change_pct)
    sec_tf_ret = sec_quote.get("perf", {}).get(tf_Lookup, 0.0)
    n50_tf_ret = n50_quote.get("perf", {}).get(tf_Lookup, 0.0)
    n500_tf_ret = n500_quote.get("perf", {}).get(tf_Lookup, 0.0)

    payload = {
        "status": "success",
        "symbol": sym,
        "exchange": exch,
        "period": p_norm,
        "quote": quote,
        "sector": canonical_sec,
        "sector_index_name": sec_meta["index_name"],
        "period_change": period_change,
        "period_change_pct": period_change_pct,
        "comparison": {
            "timeframe": p_norm,
            "stock_return": round(float(stk_tf_ret or period_change_pct), 2),
            "sector_return": round(float(sec_tf_ret or 0.0), 2),
            "nifty50_return": round(float(n50_tf_ret or 0.0), 2),
            "nifty500_return": round(float(n500_tf_ret or 0.0), 2),
            "vs_sector": round(float(stk_tf_ret or period_change_pct) - float(sec_tf_ret or 0.0), 2),
            "vs_nifty50": round(float(stk_tf_ret or period_change_pct) - float(n50_tf_ret or 0.0), 2),
            "vs_nifty500": round(float(stk_tf_ret or period_change_pct) - float(n500_tf_ret or 0.0), 2),
        },
        "candles": candles,
    }
    _HISTORY_CACHE[cache_key] = {"ts": now_ts, "payload": payload}
    return payload


# ----------------- LIVE SCREENER SNAPSHOT (single batched TradingView call, cached) ----------------- #
from pydantic import BaseModel as _LiveBM

class _LiveReq(_LiveBM):
    symbols: List[str]

_LIVE_SCREENER_CACHE: Dict[str, Any] = {"ts": 0.0, "key": "", "data": {}}

@router.post("/screener-live")
def get_screener_live(req: _LiveReq, current_user: User = Depends(get_current_user)):
    syms = sorted({s.strip().upper() for s in (req.symbols or []) if s and s.strip()})[:800]
    key = ",".join(syms)
    now_ts = time_mod.time()
    ttl = 30.0 if ScreenerEngine.is_market_open() else 300.0
    c = _LIVE_SCREENER_CACHE
    if c["key"] == key and (now_ts - c["ts"]) < ttl and c["data"]:
        return {"status": "success", "market_open": ScreenerEngine.is_market_open(), "ts": c["ts"], "data": c["data"]}
    out: Dict[str, Any] = {}
    cols = ["close", "change", "High.All", "price_52_week_high", "price_52_week_low",
            "EMA20", "EMA50", "EMA200", "RSI", "relative_volume_10d_calc",
            "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y"]
    try:
        resp = requests.post(
            "https://scanner.tradingview.com/india/scan",
            json={"symbols": {"tickers": [f"NSE:{s}" for s in syms], "query": {"types": []}}, "columns": cols},
            timeout=10,
        )
        if resp.status_code == 200:
            for row in resp.json().get("data", []):
                sym = row.get("s", "").split(":")[-1]
                d = row.get("d", [])
                if not sym or len(d) < len(cols):
                    continue
                f = lambda v: round(float(v), 2) if v is not None else None
                out[sym] = {
                    "ltp": f(d[0]), "change_pct": f(d[1]), "ath": f(d[2]), "h52": f(d[3]), "l52": f(d[4]),
                    "e21": f(d[5]), "e50": f(d[6]), "e200": f(d[7]), "rsi": f(d[8]), "vol_x": f(d[9]),
                    "p1m": f(d[10]), "p3m": f(d[11]), "p6m": f(d[12]), "p12m": f(d[13]),
                }
    except Exception as e:
        logger.warning(f"Live screener fetch failed: {e}")
    if out:
        _LIVE_SCREENER_CACHE.update({"ts": now_ts, "key": key, "data": out})
    else:
        out = c["data"]
    return {"status": "success", "market_open": ScreenerEngine.is_market_open(), "ts": now_ts, "data": out}


# ----------------- PER-USER CHART DRAWINGS PERSISTENCE ----------------- #
class ChartDrawingsPayload(BaseModel):
    symbol: str
    drawings: List[Dict[str, Any]] = []


def _ensure_drawings_table(db: Session):
    from sqlalchemy import text
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS chart_drawings (
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, symbol)
        )
    """))
    db.commit()


@router.get("/drawings")
def get_chart_drawings(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    import json
    _ensure_drawings_table(db)
    sym = symbol.strip().upper()
    row = db.execute(
        text("SELECT data FROM chart_drawings WHERE user_id = :uid AND symbol = :sym"),
        {"uid": current_user.id, "sym": sym},
    ).fetchone()
    if not row or not row[0]:
        return {"symbol": sym, "drawings": []}
    try:
        return {"symbol": sym, "drawings": json.loads(row[0])}
    except Exception:
        return {"symbol": sym, "drawings": []}


@router.put("/drawings")
def save_chart_drawings(
    payload: ChartDrawingsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    import json
    _ensure_drawings_table(db)
    sym = payload.symbol.strip().upper()
    data_str = json.dumps(payload.drawings or [])
    db.execute(
        text("""
            INSERT INTO chart_drawings (user_id, symbol, data, updated_at)
            VALUES (:uid, :sym, :data, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, symbol) DO UPDATE SET data = :data, updated_at = CURRENT_TIMESTAMP
        """),
        {"uid": current_user.id, "sym": sym, "data": data_str},
    )
    db.commit()
    return {"status": "saved", "symbol": sym, "count": len(payload.drawings or [])}


# ----------------- ZERO-LOAD PER-USER PRICE ALERTS (TELEGRAM + EMAIL) ----------------- #
class PriceAlertCreate(BaseModel):
    symbol: str
    target_price: float
    condition: str = "crossing_up"  # crossing_up | crossing_down | crossing
    notify_telegram: bool = True
    notify_email: bool = True
    note: str = ""


_LAST_ALERT_EVAL_TS: float = 0.0


def _ensure_alerts_table(db: Session):
    from sqlalchemy import text
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            target_price REAL NOT NULL,
            condition TEXT NOT NULL DEFAULT 'crossing_up',
            notify_telegram INTEGER NOT NULL DEFAULT 1,
            notify_email INTEGER NOT NULL DEFAULT 1,
            note TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            triggered_price REAL,
            triggered_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.commit()


@router.get("/alerts")
def list_price_alerts(
    symbol: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    _ensure_alerts_table(db)
    if symbol:
        rows = db.execute(
            text("SELECT id, symbol, target_price, condition, notify_telegram, notify_email, note, status, created_at FROM price_alerts WHERE user_id = :uid AND symbol = :sym AND status = 'ACTIVE' ORDER BY id DESC"),
            {"uid": current_user.id, "sym": symbol.strip().upper()},
        ).fetchall()
    else:
        rows = db.execute(
            text("SELECT id, symbol, target_price, condition, notify_telegram, notify_email, note, status, created_at FROM price_alerts WHERE user_id = :uid AND status = 'ACTIVE' ORDER BY id DESC LIMIT 100"),
            {"uid": current_user.id},
        ).fetchall()
    return {
        "alerts": [
            {
                "id": r[0], "symbol": r[1], "price": float(r[2]), "cond": r[3],
                "tg": bool(r[4]), "email": bool(r[5]), "note": r[6] or "",
                "status": r[7], "created_at": str(r[8]) if r[8] else "",
            }
            for r in rows
        ]
    }


@router.post("/alerts")
def create_price_alert(
    payload: PriceAlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    _ensure_alerts_table(db)
    sym = payload.symbol.strip().upper()
    if payload.target_price <= 0:
        raise HTTPException(status_code=400, detail="Target price must be positive")
    cond = payload.condition if payload.condition in ("crossing_up", "crossing_down", "crossing") else "crossing_up"
    res = db.execute(
        text("""
            INSERT INTO price_alerts (user_id, symbol, target_price, condition, notify_telegram, notify_email, note, status)
            VALUES (:uid, :sym, :px, :cond, :tg, :em, :note, 'ACTIVE')
        """),
        {
            "uid": current_user.id, "sym": sym, "px": round(float(payload.target_price), 2),
            "cond": cond, "tg": 1 if payload.notify_telegram else 0,
            "em": 1 if payload.notify_email else 0, "note": (payload.note or "").strip()[:160],
        },
    )
    db.commit()
    return {
        "status": "created",
        "alert": {
            "id": res.lastrowid, "symbol": sym, "price": round(float(payload.target_price), 2),
            "cond": cond, "tg": bool(payload.notify_telegram), "email": bool(payload.notify_email),
            "note": (payload.note or "").strip()[:160], "status": "ACTIVE",
        },
    }


@router.delete("/alerts/{alert_id}")
def delete_price_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import text
    _ensure_alerts_table(db)
    db.execute(
        text("DELETE FROM price_alerts WHERE id = :aid AND user_id = :uid"),
        {"aid": alert_id, "uid": current_user.id},
    )
    db.commit()
    return {"status": "deleted", "id": alert_id}


def _send_email_async(to_email: str, subject: str, body: str):
    import os, smtplib, threading
    from email.message import EmailMessage
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    pwd = os.getenv("SMTP_PASS", "").strip()
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    sender = os.getenv("SMTP_FROM", user).strip()
    if not (host and user and pwd and to_email):
        return
    def _worker():
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email
            msg.set_content(body)
            with smtplib.SMTP(host, port, timeout=10) as s:
                s.starttls()
                s.login(user, pwd)
                s.send_message(msg)
        except Exception as e:
            logger.warning(f"Price alert email failed for {to_email}: {e}")
    threading.Thread(target=_worker, daemon=True).start()


def evaluate_price_alerts(live_quotes: Dict[str, Any]):
    """Zero-load in-memory evaluator called when live_quotes already refreshes."""
    global _LAST_ALERT_EVAL_TS
    import time, threading
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.telegram_service import TelegramAlertService

    if not live_quotes:
        return
    now_ts = time.time()
    if now_ts - _LAST_ALERT_EVAL_TS < 10.0:
        return
    _LAST_ALERT_EVAL_TS = now_ts

    db = SessionLocal()
    try:
        _ensure_alerts_table(db)
        rows = db.execute(
            text("""
                SELECT a.id, a.user_id, a.symbol, a.target_price, a.condition, a.notify_telegram, a.notify_email, a.note,
                       u.username, u.email, u.telegram_chat_id
                FROM price_alerts a
                JOIN users u ON u.id = a.user_id
                WHERE a.status = 'ACTIVE'
            """)
        ).fetchall()
        if not rows:
            return

        tg_settings = None
        for r in rows:
            aid, uid, sym, target, cond, want_tg, want_em, note, uname, uemail, uchat = r
            ltp = live_quotes.get(sym)
            if ltp is None:
                continue
            try:
                ltp = float(ltp)
            except Exception:
                continue
            hit = (
                (cond == "crossing_up" and ltp >= target)
                or (cond == "crossing_down" and ltp <= target)
                or (cond == "crossing" and abs(ltp - target) / max(target, 0.01) <= 0.0025)
            )
            if not hit:
                continue

            # Mark TRIGGERED atomically before notifying so multi-worker setups never double-fire
            upd = db.execute(
                text("UPDATE price_alerts SET status = 'TRIGGERED', triggered_price = :ltp, triggered_at = CURRENT_TIMESTAMP WHERE id = :aid AND status = 'ACTIVE'"),
                {"ltp": ltp, "aid": aid},
            )
            db.commit()
            if upd.rowcount == 0:
                continue

            cond_txt = "crossed above" if cond == "crossing_up" else ("crossed below" if cond == "crossing_down" else "reached")
            note_line = f"\nNote: {note}" if note else ""
            msg_tg = (
                f"<b>AlphaQuant Price Alert — {sym}</b>\n"
                f"{sym} {cond_txt} <b>₹{target:,.2f}</b>\n"
                f"Live LTP: <b>₹{ltp:,.2f}</b>{note_line}"
            )
            msg_email = (
                f"AlphaQuant Price Alert — {sym}\n\n"
                f"{sym} {cond_txt} Rs {target:,.2f}\n"
                f"Live LTP: Rs {ltp:,.2f}{note_line}\n\n"
                f"https://alphaquanttechnolgy.com/"
            )

            if want_tg:
                if tg_settings is None:
                    tg_settings = TelegramAlertService.get_settings(db)
                bot_tok = getattr(tg_settings, "bot_token", None)
                # Send ONLY to the individual user's personal Telegram Chat ID (never the shared group)
                chat_id = (uchat or "").strip()
                if bot_tok and chat_id:
                    logger.info(f"Sending Private Price Alert Telegram for {sym} (user={uname}, ltp={ltp}, target={target}) to chat_id={chat_id}")
                    threading.Thread(
                        target=TelegramAlertService.send_message,
                        args=(bot_tok, chat_id, msg_tg),
                        daemon=True,
                    ).start()
                else:
                    logger.warning(f"Private Price Alert Telegram skipped for {sym} (user={uname}): personal telegram_chat_id not linked")

            if want_em and uemail:
                _send_email_async(uemail, f"AlphaQuant Alert: {sym} at ₹{ltp:,.2f}", msg_email)
    except Exception as e:
        logger.warning(f"evaluate_price_alerts error: {e}")
    finally:
        db.close()
