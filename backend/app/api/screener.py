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
    current_user: Optional[User] = Depends(get_current_user)
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
