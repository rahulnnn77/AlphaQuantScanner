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
    
    # Filter universe if requested
    is_fo_only = (universe.lower() == "fo")
    
    filtered_results = {}
    counts = {}
    for tf_key, items in results_by_tf.items():
        if is_fo_only:
            tf_items = [it for it in items if it.get("is_fo")]
        else:
            tf_items = items
        filtered_results[tf_key] = tf_items
        counts[tf_key] = len(tf_items)

    return {
        "status": "success",
        "last_updated": last_updated,
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
    across daily, weekly, and monthly timeframes.
    Supports filtering by universe (Nifty 500 vs Nifty F&O).
    """
    import os, json
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
    last_updated = data.get("last_updated", "Recent")
    
    is_fo_only = (universe.lower() == "fo")
    
    filtered_results = {}
    counts = {}
    
    for tf_key, level_dict in results_by_tf.items():
        filtered_results[tf_key] = {}
        counts[tf_key] = {}
        for l_key, items in level_dict.items():
            if is_fo_only:
                l_items = [it for it in items if it.get("is_fo")]
            else:
                l_items = items
            filtered_results[tf_key][l_key] = l_items
            counts[tf_key][l_key] = len(l_items)

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
        "last_updated": last_updated,
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
