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
    }
    yf_range, yf_interval = period_map.get(p_norm, ("1mo", "1d"))
    yf_suffix = ".BO" if exch == "BSE" else ".NS"
    yf_ticker = f"{sym}{yf_suffix}"

    cache_key = f"{exch}:{sym}:{p_norm}"
    now_ts = time_mod.time()
    cached = _HISTORY_CACHE.get(cache_key)
    if cached and (now_ts - cached["ts"] < 60.0):
        return cached["payload"]

    quote_map = _fetch_batch_quotes_and_benchmarks([f"{exch}:{sym}"])
    quote = quote_map.get(f"{exch}:{sym}", {})
    canonical_sec = quote.get("sector") or _classify_canonical_sector(sym, None, None, sym)
    sec_meta = SECTOR_BENCHMARKS.get(canonical_sec) or SECTOR_BENCHMARKS["Capital Goods"]
    sec_quote = quote_map.get(sec_meta["tv_ticker"], {})
    n50_quote = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_50"], {})
    n500_quote = quote_map.get(MARKET_BENCHMARK_TICKERS["NIFTY_500"], {})

    candles = []
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
        )
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
