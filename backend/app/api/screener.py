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
def get_market_breadth_data():
    """
    Returns Market Breadth Analyzer data:
    - Index Performance: Nifty 50, Sensex, Bank Nifty, and all sectoral indices
    - Top 10 Gainers % (Symbol, % chg, Ltp) based on Friday's official close
    - Top 10 Losers % (Symbol, % chg, Ltp)
    - Advance / Decline Summary
    """
    return ScreenerEngine.get_market_breadth()

@router.get("/index-stocks")
def get_index_stocks(index: str = Query("NIFTY 50", description="Index symbol, e.g. NIFTY 50, BANK NIFTY, NIFTY IT")):
    """
    Returns the underlying constituent stocks for the selected index.
    """
    return ScreenerEngine.get_index_stocks(index)

@router.get("/hps")
def get_hps_stocks(
    timeframe: str = Query("daily", description="Timeframe: 4h, daily, weekly, monthly, all"),
    universe: str = Query("nifty500", description="Universe: nifty500, fo")
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

    import pytz
    from datetime import datetime
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    day_suffix = "th" if 11 <= now_ist.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(now_ist.day % 10, "th")
    formatted_date = now_ist.strftime(f"%A {now_ist.day}{day_suffix} %b")
    is_weekday = now_ist.weekday() < 5
    is_market_open = is_weekday and ((now_ist.hour == 9 and now_ist.minute >= 15) or (10 <= now_ist.hour < 15) or (now_ist.hour == 15 and now_ist.minute <= 30))
    if is_market_open:
        live_timestamp = f"Live: {formatted_date} ({now_ist.strftime('%I:%M%p').lower().lstrip('0')})"
    else:
        live_timestamp = f"{formatted_date} Close (3:30pm)"

    # Filter universe if requested and enrich with live LTP
    is_fo_only = (universe.lower() == "fo")
    
    filtered_results = {}
    counts = {}
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
            enriched_items.append(item_copy)
        filtered_results[tf_key] = enriched_items
        counts[tf_key] = len(enriched_items)

    return {
        "status": "success",
        "last_updated": live_timestamp,
        "universe": universe.upper(),
        "counts": counts,
        "timeframe": timeframe,
        "data": filtered_results if timeframe == "all" else filtered_results.get(timeframe.lower(), [])
    }

@router.get("/hps-mean-reversion")
def get_hps_mean_reversion_stocks(
    timeframe: str = Query("daily", description="Timeframe: daily, weekly, monthly, all"),
    level: str = Query("all", description="Level: level1, level2, level3, all"),
    universe: str = Query("nifty500", description="Universe: nifty500, fo")
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

    import pytz
    from datetime import datetime
    ist = pytz.timezone("Asia/Kolkata")
    now_ist = datetime.now(ist)
    day_suffix = "th" if 11 <= now_ist.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(now_ist.day % 10, "th")
    formatted_date = now_ist.strftime(f"%A {now_ist.day}{day_suffix} %b")
    is_weekday = now_ist.weekday() < 5
    is_market_open = is_weekday and ((now_ist.hour == 9 and now_ist.minute >= 15) or (10 <= now_ist.hour < 15) or (now_ist.hour == 15 and now_ist.minute <= 30))
    if is_market_open:
        live_timestamp = f"Live: {formatted_date} ({now_ist.strftime('%I:%M%p').lower().lstrip('0')})"
    else:
        live_timestamp = f"{formatted_date} Close (3:30pm)"
    
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
