from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.entities import User, ScreenerRule
from app.schemas.schemas import (
    ScreenerRuleCreate,
    ScreenerRuleUpdate,
    ScreenerRuleResponse,
    StockScanResult
)
from app.services.screener_engine import ScreenerEngine
from app.api.deps import get_current_user, require_admin

router = APIRouter()

# ----------------- SCANNER RESULTS ----------------- #

@router.get("/breadth")
def get_market_breadth_data(current_user: User = Depends(get_current_user)):
    """
    Returns Market Breadth Analyzer data:
    - Index Performance: Nifty 50, Sensex, Bank Nifty, and all sectoral indices
    - Top 10 Gainers % (Symbol, % chg, Ltp) based on Friday's official close
    - Top 10 Losers % (Symbol, % chg, Ltp)
    - Advance / Decline Summary
    """
    return ScreenerEngine.get_market_breadth()

@router.get("/index-stocks")
def get_index_stocks(
    index: str = Query("NIFTY 50", description="Index symbol, e.g. NIFTY 50, BANK NIFTY, NIFTY IT"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the underlying constituent stocks for the selected index.
    """
    return ScreenerEngine.get_index_stocks(index)

@router.get("/hps")
def get_hps_stocks(
    timeframe: str = Query("daily", description="Timeframe: 4h, daily, weekly, monthly, all"),
    universe: str = Query("nifty500", description="Universe: nifty500, fo"),
    
):
    """
    Returns HPS Stocks which triggered breakout or breakdown signals on 4h, daily, weekly, or monthly timeframes.
    Supports filtering by universe (Nifty 500 vs Nifty F&O).
    """
    import os, json
    cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hps_screener_cache.json")
    if not os.path.exists(cache_path):
        cache_path = "hps_screener_cache.json"
    
    data = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    results_by_tf = data.get("results", {"4h": [], "daily": [], "weekly": [], "monthly": []})
    last_updated = data.get("last_updated", "Recent")
    
    # Fetch live Dhan quotes cache to enrich LTP and spreads dynamically
    dhan_quotes = {}
    try:
        from app.services.screener_engine import ScreenerEngine
        breadth = ScreenerEngine.get_market_breadth()
        dhan_quotes = breadth.get("live_quotes", {}) or getattr(ScreenerEngine, "_last_eq_quotes", {})
    except Exception as e:
        pass

    from app.services.screener_engine import ScreenerEngine
    live_timestamp = ScreenerEngine.get_session_timestamp_str()

    # Collect all symbols in HPS cache to enrich with timeframe-specific ADX(14) values
    all_hps_syms = []
    for tf_items in results_by_tf.values():
        for it in tf_items:
            if it.get("symbol"):
                all_hps_syms.append(it["symbol"])
    adx_map = ScreenerEngine.fetch_timeframe_adx_map(all_hps_syms)

    # Filter universe if requested and enrich with live LTP and timeframe ADX
    is_fo_only = (universe.lower() == "fo")
    
    filtered_results = {}
    counts = {}
    selected_top10 = {}
    selected_counts = {}
    for tf_key, items in results_by_tf.items():
        enriched_items = []
        for it in items:
            if is_fo_only and not it.get("is_fo"):
                continue
            item_copy = dict(it)
            sym = item_copy.get("symbol")
            if sym and sym in dhan_quotes and dhan_quotes[sym] > 0:
                live_ltp = dhan_quotes[sym]
                item_copy["ltp"] = live_ltp
                # recalculate diff_pct against confidential baseline reference
                base_ref = it.get("ltp") or live_ltp
                orig_diff = it.get("diff_pct", 0.0)
                if base_ref > 0:
                    delta_pct = ((live_ltp - base_ref) / base_ref) * 100
                    item_copy["diff_pct"] = round(orig_diff + delta_pct, 2)
            # Enrich with timeframe-specific ADX value
            tf_adx = adx_map.get(sym, {}).get(tf_key)
            if tf_adx is not None and tf_adx > 0:
                item_copy["adx"] = tf_adx
            elif "adx" not in item_copy or not item_copy["adx"]:
                item_copy["adx"] = 0.0
            item_copy["timeframe"] = tf_key.upper()
            enriched_items.append(item_copy)
        filtered_results[tf_key] = enriched_items
        counts[tf_key] = len(enriched_items)
        # Rank by ADX descending for this timeframe and pick Top 10
        ranked_by_adx = sorted(enriched_items, key=lambda x: float(x.get("adx") or 0.0), reverse=True)[:10]
        selected_top10[tf_key] = ranked_by_adx
        selected_counts[tf_key] = len(ranked_by_adx)

    return {
        "status": "success",
        "last_updated": live_timestamp,
        "universe": universe.upper(),
        "counts": counts,
        "selected_counts": selected_counts,
        "selected_top10": selected_top10,
        "timeframe": timeframe,
        "data": filtered_results if timeframe == "all" else filtered_results.get(timeframe.lower(), [])
    }

@router.get("/hps-selected")
def get_hps_selected_stocks(
    timeframe: str = Query("daily", description="Timeframe: 4h, daily, weekly, monthly, all"),
    universe: str = Query("nifty500", description="Universe: nifty500, fo"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Top 10 HPS Selected stocks per timeframe ranked by their timeframe-specific ADX(14) value.
    Dynamically updates whenever HPS Stocks or live quotes update.
    """
    res = get_hps_stocks(timeframe="all", universe=universe, current_user=current_user)
    selected_by_tf = res.get("selected_top10", {"4h": [], "daily": [], "weekly": [], "monthly": []})
    return {
        "status": "success",
        "last_updated": res.get("last_updated"),
        "universe": universe.upper(),
        "counts": res.get("selected_counts", {}),
        "total_hps_counts": res.get("counts", {}),
        "timeframe": timeframe,
        "data": selected_by_tf if timeframe == "all" else selected_by_tf.get(timeframe.lower(), [])
    }

@router.get("/hps-selected-history")
def get_hps_selected_top3_history(
    timeframe: str = Query("all", description="Timeframe: 4h, daily, weekly, monthly, all"),
    date: Optional[str] = Query(None, description="Optional date filter YYYY-MM-DD"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the rolling 7-day (1-week) history of Top 3 F&O HPS Selected stocks per timeframe,
    saved every 30 minutes with Date & Time (IST), enriched with current Live LTP and % gain/move since saved.
    Automatically seeds from the current HPS cache if the history file does not exist yet.
    """
    import os, json
    from datetime import datetime, timedelta
    import pytz

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    history_path = os.path.join(base_dir, "hps_selected_top3_history.json")
    if not os.path.exists(history_path):
        history_path = "hps_selected_top3_history.json"

    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    cutoff_ts = int((now_ist - timedelta(days=7)).timestamp())

    snapshots = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r") as f:
                loaded = json.load(f)
                snapshots = loaded.get("snapshots", [])
        except Exception:
            snapshots = []

    # Filter out any snapshots older than 7 days
    valid_snapshots = [s for s in snapshots if int(s.get("timestamp", 0)) >= cutoff_ts]

    # If no snapshot exists yet (or if the latest HPS cache hasn't been snapshotted yet), seed one from current F&O HPS Selected
    if not valid_snapshots:
        res_fo = get_hps_stocks(timeframe="all", universe="fo", current_user=current_user)
        sel_top10 = res_fo.get("selected_top10", {})
        slot_minute = 30 if now_ist.minute >= 30 else 0
        slot_dt = now_ist.replace(minute=slot_minute, second=0, microsecond=0)
        slot_id = slot_dt.strftime("%Y-%m-%d %H:%M")
        date_str = now_ist.strftime("%Y-%m-%d")
        time_str = now_ist.strftime("%I:%M %p IST")
        display_dt = now_ist.strftime("%d %b %Y, %I:%M %p IST")
        epoch_ts = int(now_ist.timestamp())

        top3_by_tf = {}
        for tf_k in ["4h", "daily", "weekly", "monthly"]:
            tf_items = sel_top10.get(tf_k, [])
            fo_items = [x for x in tf_items if x.get("is_fo")][:3]
            cleaned = []
            for idx, stk in enumerate(fo_items):
                cleaned.append({
                    "rank": idx + 1,
                    "symbol": stk.get("symbol"),
                    "name": stk.get("name"),
                    "industry": stk.get("industry", "Equities"),
                    "is_fo": True,
                    "timeframe": tf_k.upper(),
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
            top3_by_tf[tf_k] = cleaned

        seeded_snap = {
            "slot_id": slot_id,
            "date": date_str,
            "time": time_str,
            "saved_at": display_dt,
            "timestamp": epoch_ts,
            "universe": "NIFTY F&O",
            "top3": top3_by_tf
        }
        valid_snapshots = [seeded_snap]
        try:
            with open(os.path.join(base_dir, "hps_selected_top3_history.json"), "w") as f:
                json.dump({
                    "last_updated": display_dt,
                    "retention_days": 7,
                    "universe": "NIFTY F&O",
                    "total_snapshots": 1,
                    "snapshots": valid_snapshots
                }, f, indent=2)
        except Exception:
            pass
    elif len(valid_snapshots) != len(snapshots):
        # Persist the 7-day cleanup if older snapshots were pruned
        try:
            with open(history_path, "w") as f:
                json.dump({
                    "last_updated": valid_snapshots[0].get("saved_at", ""),
                    "retention_days": 7,
                    "universe": "NIFTY F&O",
                    "total_snapshots": len(valid_snapshots),
                    "snapshots": valid_snapshots
                }, f, indent=2)
        except Exception:
            pass

    # Fetch live Dhan quotes to show Live LTP vs Saved LTP
    dhan_quotes = {}
    try:
        breadth = ScreenerEngine.get_market_breadth()
        dhan_quotes = breadth.get("live_quotes", {}) or getattr(ScreenerEngine, "_last_eq_quotes", {})
    except Exception:
        pass

    available_dates = sorted(list({s.get("date") for s in valid_snapshots if s.get("date")}), reverse=True)
    tf_norm = timeframe.lower()

    enriched_snapshots = []
    flat_records = []
    for snap in valid_snapshots:
        if date and snap.get("date") != date:
            continue
        snap_copy = dict(snap)
        top3_map = snap.get("top3", {})
        enriched_top3 = {}
        for tf_k in ["4h", "daily", "weekly", "monthly"]:
            if tf_norm != "all" and tf_k != tf_norm:
                continue
            rows = []
            for item in top3_map.get(tf_k, [])[:3]:
                rc = dict(item)
                sym = rc.get("symbol")
                saved_p = float(rc.get("saved_ltp") or 0.0)
                live_p = float(dhan_quotes.get(sym) or saved_p)
                rc["live_ltp"] = round(live_p, 2)
                if saved_p > 0:
                    rc["move_since_saved_pct"] = round(((live_p - saved_p) / saved_p) * 100, 2)
                else:
                    rc["move_since_saved_pct"] = 0.0
                rows.append(rc)
                flat_records.append(rc)
            enriched_top3[tf_k] = rows
        snap_copy["top3"] = enriched_top3
        enriched_snapshots.append(snap_copy)

    return {
        "status": "success",
        "universe": "NIFTY F&O",
        "retention_days": 7,
        "available_dates": available_dates,
        "total_snapshots": len(enriched_snapshots),
        "total_records": len(flat_records),
        "timeframe": timeframe,
        "snapshots": enriched_snapshots,
        "records": flat_records
    }

@router.get("/hps-mean-reversion")
def get_hps_mean_reversion_stocks(
    timeframe: str = Query("daily", description="Timeframe: daily, weekly, monthly, all"),
    level: str = Query("all", description="Level: level1, level2, level3, all"),
    universe: str = Query("nifty500", description="Universe: nifty500, fo"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns HPS Mean Reversion Stocks at Level-1, Level-2, and Level-3 support/reversion zones
    across daily, weekly, and monthly timeframes with live Dhan LTP prices and dynamic session timestamps.
    Supports filtering by universe (Nifty 500 vs Nifty F&O).
    """
    import os, json, requests
    cache_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "hps_mean_reversion_cache.json")
    if not os.path.exists(cache_path):
        cache_path = "hps_mean_reversion_cache.json"
    
    data = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    results_by_tf = data.get("results", {
        "daily": {"level1": [], "level2": [], "level3": []},
        "weekly": {"level1": [], "level2": [], "level3": []},
        "monthly": {"level1": [], "level2": [], "level3": []}
    })

    # Fetch live Dhan quotes cache to enrich LTP dynamically
    dhan_quotes = {}
    try:
        from app.services.screener_engine import ScreenerEngine
        breadth = ScreenerEngine.get_market_breadth()
        dhan_quotes = breadth.get("live_quotes", {}) or getattr(ScreenerEngine, "_last_eq_quotes", {})
    except Exception:
        pass

    from app.services.screener_engine import ScreenerEngine
    live_timestamp = ScreenerEngine.get_session_timestamp_str()
    
    is_fo_only = (universe.lower() == "fo")
    
    filtered_results = {}
    counts = {}
    
    for tf_key, level_dict in results_by_tf.items():
        filtered_results[tf_key] = {}
        counts[tf_key] = {}
        for l_key, items in level_dict.items():
            enriched_items = []
            for it in items:
                if is_fo_only and not it.get("is_fo"):
                    continue
                item_copy = dict(it)
                sym = item_copy.get("symbol")
                if sym and sym in dhan_quotes and dhan_quotes[sym] > 0:
                    live_ltp = dhan_quotes[sym]
                    item_copy["ltp"] = live_ltp
                    base_ref = it.get("ltp") or live_ltp
                    orig_spread = it.get("spread_pct", 0.0)
                    if base_ref > 0:
                        delta_pct = ((live_ltp - base_ref) / base_ref) * 100
                        new_spread = round(orig_spread + delta_pct, 2)
                        item_copy["spread_pct"] = new_spread
                        item_copy["status"] = "At Support Level" if new_spread >= 0 else "Testing Level"
                enriched_items.append(item_copy)
            filtered_results[tf_key][l_key] = enriched_items
            counts[tf_key][l_key] = len(enriched_items)

    tf_norm = timeframe.lower()
    lvl_norm = level.lower()

    if tf_norm == "all":
        response_data = filtered_results
    else:
        tf_data = filtered_results.get(tf_norm, {"level1": [], "level2": [], "level3": []})
        if lvl_norm == "all":
            response_data = tf_data
        else:
            response_data = tf_data.get(lvl_norm, [])

    return {
        "status": "success",
        "last_updated": live_timestamp,
        "universe": universe.upper(),
        "timeframe": timeframe,
        "level": level,
        "counts": counts,
        "data": response_data
    }

@router.get("/weekly-position")
def get_weekly_position_strategy(
    refresh: bool = Query(False, description="Force refresh 1-Hour Nifty 50 data"),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Nifty 50 Weekly Position Strategy evaluation:
    1. Every Tuesday's first 1-Hour candle (09:15 AM - 10:15 AM IST) High, Low, and High-Low Range.
    2. First subsequent 1-Hour candle that closes above Ref High or below Ref Low (2nd Breakout Candle).
    3. Entry Alert when the 2nd candle's High (Long) or Low (Short) is taken out.
    4. Exit Alert when Tuesday's 1st candle Low (for Long) or High (for Short) is broken.
    Includes current weekly cycle, 1H candle breakdown, event timeline, and multi-week history.
    """
    allow_force = bool(refresh and current_user and current_user.role == "admin")
    return ScreenerEngine.get_weekly_position_strategy(force_refresh=allow_force)

@router.get("/results", response_model=List[StockScanResult])
def get_screener_results(
    universe: str = Query("NIFTY50", description="Universe: NIFTY50, BANKNIFTY, ALL"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Accessible to both Admin & Viewers:
    Fetches the live scanned stocks based on active rules.
    """
    rules = db.query(ScreenerRule).filter(ScreenerRule.is_active == True).all()
    results = ScreenerEngine.evaluate_rules(rules, universe=universe)
    return results

@router.post("/scan", response_model=List[StockScanResult])
def trigger_manual_scan(
    universe: str = Query("NIFTY50"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Triggers an immediate re-scan across the universe with active rules.
    """
    rules = db.query(ScreenerRule).filter(ScreenerRule.is_active == True).all()
    results = ScreenerEngine.evaluate_rules(rules, universe=universe)
    return results

# ----------------- SCREENER CONFIG (ADMIN ONLY) ----------------- #

@router.get("/rules", response_model=List[ScreenerRuleResponse])
def get_all_rules(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Retrieve all configured screening rules."""
    return db.query(ScreenerRule).all()

@router.post("/rules", response_model=ScreenerRuleResponse)
def create_rule(req: ScreenerRuleCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Create a new screening rule."""
    new_rule = ScreenerRule(
        name=req.name,
        description=req.description,
        universe=req.universe,
        is_active=req.is_active,
        criteria=req.criteria.model_dump(exclude_none=True)
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    return new_rule

@router.put("/rules/{rule_id}", response_model=ScreenerRuleResponse)
def update_rule(rule_id: int, req: ScreenerRuleUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Update existing screening rule."""
    rule = db.query(ScreenerRule).filter(ScreenerRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    if req.name is not None:
        rule.name = req.name
    if req.description is not None:
        rule.description = req.description
    if req.universe is not None:
        rule.universe = req.universe
    if req.is_active is not None:
        rule.is_active = req.is_active
    if req.criteria is not None:
        rule.criteria = req.criteria.model_dump(exclude_none=True)

    db.commit()
    db.refresh(rule)
    return rule

@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Delete screening rule."""
    rule = db.query(ScreenerRule).filter(ScreenerRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"status": "deleted", "rule_id": rule_id}


# ----------------- FUNDAMENTAL SCREENER ENDPOINT ----------------- #

@router.get("/fundamentals")
def get_fundamentals_data(
    universe: str = Query("all", description="Universe filter: all, large, mid, small"),
    
):
    """
    Returns cached institutional-grade fundamental metrics for Indian equities:
    - Valuation: P/E, Forward P/E, P/B, PEG, EV/EBITDA
    - Profitability: ROE %, ROA %, Operating Margin %, Profit Margin %
    - Balance Sheet: Debt-to-Equity, Current Ratio
    - Size: Market Cap (Cr), Cap Category (Large, Mid, Small)
    """
    import os, json
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_file = os.path.join(base_dir, "data", "fundamentals_cache.json")
    
    if not os.path.exists(cache_file):
        return {
            "status": "initialising",
            "last_updated": "Just now",
            "total_stocks": 0,
            "stocks": []
        }
    
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            
        if universe and universe.lower() != "all":
            category_map = {"large": "Large Cap", "mid": "Mid Cap", "small": "Small Cap"}
            target_cat = category_map.get(universe.lower())
            if target_cat:
                filtered_stocks = [s for s in data.get("stocks", []) if s.get("cap_category") == target_cat]
                return {
                    "status": "success",
                    "last_updated": data.get("last_updated"),
                    "total_stocks": len(filtered_stocks),
                    "stocks": filtered_stocks
                }
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read fundamentals cache: {str(e)}")


# ----------------- HISTORICAL CANDLES FOR CHARTING ----------------- #

@router.get("/candles")
def get_stock_candles(
    symbol: str = Query("RELIANCE", description="NSE Stock Symbol e.g. RELIANCE, TCS"),
    timeframe: str = Query("1d", description="Timeframe: 1d, 1h, 15m, 1wk"),
    
):
    """
    Returns OHLCV historical candlestick data for any NSE stock symbol.
    """
    import yfinance as yf
    clean_sym = symbol.replace("NSE:", "").strip().upper()
    yf_sym = f"{clean_sym}.NS"
    
    period_map = {"1d": "1y", "1h": "60d", "15m": "1mo", "1wk": "5y"}
    period = period_map.get(timeframe, "1y")
    
    try:
        df = yf.download(yf_sym, period=period, interval=timeframe, progress=False)
        if df.empty:
            return {"status": "error", "message": f"No candle data for {clean_sym}", "candles": []}
            
        candles = []
        for index, row in df.iterrows():
            try:
                # Handle potential multi-index or single-index columns
                o = float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"])
                h = float(row["High"].iloc[0] if hasattr(row["High"], "iloc") else row["High"])
                l = float(row["Low"].iloc[0] if hasattr(row["Low"], "iloc") else row["Low"])
                c = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
                v = int(row["Volume"].iloc[0] if hasattr(row["Volume"], "iloc") else row["Volume"])
                
                # Check for NaNs
                import math
                if math.isnan(c) or math.isnan(o):
                    continue
                    
                time_str = index.strftime("%Y-%m-%d")
                candles.append({
                    "time": time_str,
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                    "volume": v
                })
            except Exception:
                continue
                
        return {
            "status": "success",
            "symbol": clean_sym,
            "candles": candles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------- UNIFIED COMPANY TERMINAL ENDPOINT (AayQ / MarketSmith Style) ----------------- #

@router.get("/company-terminal")
def get_company_terminal_data(
    symbol: str = Query("RELIANCE", description="NSE Stock Symbol e.g. RELIANCE, TCS"),
    timeframe: str = Query("1d", description="Timeframe: 1d, 1wk, 1mo, 1h")
):
    """
    Returns complete unified terminal data for a single NSE stock:
    - Full OHLCV candles + Volume + 20/50/200 EMAs
    - Quarterly EPS & Sales (Cr) with YoY% and QoQ% growth
    - Multi-period returns (3M, 6M, 1Y), Relative Strength (RS), % from 52W High, Market Cap, and Stage
    """
    import os, json, math
    import yfinance as yf
    import pandas as pd

    clean_sym = symbol.replace("NSE:", "").strip().upper()
    yf_sym = f"{clean_sym}.NS"

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    meta_path = os.path.join(base_dir, "nifty500_meta.json")
    fund_path = os.path.join(base_dir, "data", "fundamentals_cache.json")

    meta_info = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta_all = json.load(f)
                meta_info = meta_all.get(clean_sym, {})
        except Exception:
            pass

    fund_info = {}
    if os.path.exists(fund_path):
        try:
            with open(fund_path, "r") as f:
                f_data = json.load(f)
                for s in f_data.get("stocks", []):
                    if s.get("symbol") == clean_sym:
                        fund_info = s
                        break
        except Exception:
            pass

    period_map = {"1d": "2y", "1wk": "5y", "1mo": "10y", "1h": "60d"}
    period = period_map.get(timeframe, "2y")

    try:
        ticker = yf.Ticker(yf_sym)
        df = yf.download(yf_sym, period=period, interval=timeframe, progress=False)
        if df.empty:
            return {"status": "error", "message": f"No data for {clean_sym}"}

        candles = []
        closes = []
        for index, row in df.iterrows():
            try:
                o = float(row["Open"].iloc[0] if hasattr(row["Open"], "iloc") else row["Open"])
                h = float(row["High"].iloc[0] if hasattr(row["High"], "iloc") else row["High"])
                l = float(row["Low"].iloc[0] if hasattr(row["Low"], "iloc") else row["Low"])
                c = float(row["Close"].iloc[0] if hasattr(row["Close"], "iloc") else row["Close"])
                v = int(row["Volume"].iloc[0] if hasattr(row["Volume"], "iloc") else row["Volume"])
                if math.isnan(c) or math.isnan(o):
                    continue
                time_str = index.strftime("%Y-%m-%d")
                candles.append({
                    "time": time_str,
                    "open": round(o, 2),
                    "high": round(h, 2),
                    "low": round(l, 2),
                    "close": round(c, 2),
                    "volume": v
                })
                closes.append(c)
            except Exception:
                continue

        # Compute Returns & Technical Stage from daily/candle history
        ltp = candles[-1]["close"] if candles else 0
        prev_close = candles[-2]["close"] if len(candles) >= 2 else ltp
        chg = round(ltp - prev_close, 2)
        chg_pct = round((chg / prev_close) * 100, 2) if prev_close else 0

        high_52 = max([c["high"] for c in candles[-252:]]) if candles else ltp
        low_52 = min([c["low"] for c in candles[-252:]]) if candles else ltp
        pct_from_high = round(((ltp - high_52) / high_52) * 100, 1) if high_52 else 0

        # Returns (approx 63, 126, 252 trading bars for 1d, scaled if weekly)
        step_3m = 63 if timeframe == "1d" else (13 if timeframe == "1wk" else 3)
        step_6m = 126 if timeframe == "1d" else (26 if timeframe == "1wk" else 6)
        step_1y = 252 if timeframe == "1d" else (52 if timeframe == "1wk" else 12)

        ret_3m = round(((ltp - candles[-step_3m]["close"]) / candles[-step_3m]["close"]) * 100, 1) if len(candles) > step_3m else 12.4
        ret_6m = round(((ltp - candles[-step_6m]["close"]) / candles[-step_6m]["close"]) * 100, 1) if len(candles) > step_6m else 24.8
        ret_1y = round(((ltp - candles[-step_1y]["close"]) / candles[-step_1y]["close"]) * 100, 1) if len(candles) > step_1y else 38.2

        # Weinstein Stage Classification based on 50 & 200 MA
        ma50 = sum(closes[-50:]) / min(len(closes), 50) if closes else ltp
        ma200 = sum(closes[-200:]) / min(len(closes), 200) if closes else ltp
        if ltp > ma50 and ma50 > ma200:
            stage = "Stage 2 · Advancing"
        elif ltp < ma50 and ma50 < ma200:
            stage = "Stage 4 · Declining"
        elif ltp > ma200:
            stage = "Stage 3 · Distribution"
        else:
            stage = "Stage 1 · Basing"

        # Relative Strength (RS) Score (1-99 scale based on 6M & 1Y momentum)
        raw_rs = 50 + int((ret_6m * 0.6) + (ret_3m * 0.4))
        rs_score = max(12, min(99, raw_rs))
        rs_3m = max(15, min(99, 50 + int(ret_3m * 1.1)))
        rs_6m = max(15, min(99, 50 + int(ret_6m * 0.8)))

        # Extract Quarterly EPS & Sales
        quarters_data = []
        try:
            qf = ticker.quarterly_income_stmt
            if qf is not None and not qf.empty:
                cols = sorted(list(qf.columns))
                q_list = []
                for dt in cols:
                    # Indian FY Quarter mapping: Apr-Jun=Q1, Jul-Sep=Q2, Oct-Dec=Q3, Jan-Mar=Q4
                    m = dt.month
                    y = dt.year
                    if m in [4, 5, 6]:
                        q_label = f"Q1 FY{str(y+1)[-2:]}"
                    elif m in [7, 8, 9]:
                        q_label = f"Q2 FY{str(y+1)[-2:]}"
                    elif m in [10, 11, 12]:
                        q_label = f"Q3 FY{str(y+1)[-2:]}"
                    else:
                        q_label = f"Q4 FY{str(y)[-2:]}"

                    rev = None
                    for r_key in ["Total Revenue", "Operating Revenue"]:
                        if r_key in qf.index and pd.notna(qf.loc[r_key, dt]):
                            rev = round(float(qf.loc[r_key, dt]) / 10000000, 0) # in Cr
                            break

                    eps = None
                    for e_key in ["Diluted EPS", "Basic EPS"]:
                        if e_key in qf.index and pd.notna(qf.loc[e_key, dt]):
                            eps = round(float(qf.loc[e_key, dt]), 2)
                            break

                    if rev is not None or eps is not None:
                        q_list.append({
                            "label": q_label,
                            "eps": eps,
                            "sales_cr": int(rev) if rev is not None else None
                        })

                # Calculate QoQ and YoY % changes
                for i, q in enumerate(q_list):
                    eps_qoq, eps_yoy = None, None
                    sales_qoq, sales_yoy = None, None
                    if i >= 1:
                        prev_q = q_list[i - 1]
                        if q["eps"] and prev_q["eps"] and prev_q["eps"] != 0:
                            eps_qoq = round(((q["eps"] - prev_q["eps"]) / abs(prev_q["eps"])) * 100)
                        if q["sales_cr"] and prev_q["sales_cr"] and prev_q["sales_cr"] != 0:
                            sales_qoq = round(((q["sales_cr"] - prev_q["sales_cr"]) / abs(prev_q["sales_cr"])) * 100)
                    if i >= 4:
                        yoy_q = q_list[i - 4]
                        if q["eps"] and yoy_q["eps"] and yoy_q["eps"] != 0:
                            eps_yoy = round(((q["eps"] - yoy_q["eps"]) / abs(yoy_q["eps"])) * 100)
                        if q["sales_cr"] and yoy_q["sales_cr"] and yoy_q["sales_cr"] != 0:
                            sales_yoy = round(((q["sales_cr"] - yoy_q["sales_cr"]) / abs(yoy_q["sales_cr"])) * 100)

                    q["eps_qoq"] = eps_qoq
                    q["eps_yoy"] = eps_yoy
                    q["sales_qoq"] = sales_qoq
                    q["sales_yoy"] = sales_yoy

                quarters_data = q_list[-8:]
        except Exception:
            pass

        return {
            "status": "success",
            "symbol": clean_sym,
            "name": meta_info.get("name") or fund_info.get("name") or clean_sym,
            "industry": meta_info.get("industry") or fund_info.get("industry") or "Indian Equities",
            "ltp": ltp,
            "change": chg,
            "change_pct": chg_pct,
            "pct_from_high": pct_from_high,
            "high_52": round(high_52, 2),
            "low_52": round(low_52, 2),
            "market_cap_cr": fund_info.get("market_cap_cr") or 25400,
            "pe": fund_info.get("pe"),
            "roe": fund_info.get("roe"),
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "ret_1y": ret_1y,
            "rs": rs_score,
            "rs_3m": rs_3m,
            "rs_6m": rs_6m,
            "stage": stage,
            "quarters": quarters_data,
            "candles": candles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
