# Product Requirements Document (PRD)
## AlphaQuant Scanner - Institutional Market Screener & Real-Time Alert Engine

### 1. Executive Summary
AlphaQuant Scanner is a quantitative market scanning, technical analysis, and automated trade signal terminal tailored for Indian equity markets (NSE). The platform operates over the entire NIFTY 500 universe and the complete NIFTY F&O derivatives constituent list, providing institutional-grade dynamic support detection, breakout tracking, market breadth analytics, and real-time alert dispatching via Telegram.

---

### 2. Core Screeners & Algorithms

#### 2.1 HPS Stocks (Breakout Tracker)
- **Objective**: Track institutional momentum breakouts and breakdown transitions across multiple timeframes.
- **Timeframes**: 4-Hour (4H), Daily (1D), Weekly (1W), Monthly (1M).
- **Universes**: NIFTY 500 (500 Stocks), NIFTY F&O (213 Active Equities).
- **Signals**:
  - `Bullish Breakout`: Price breaks above key dynamic threshold.
  - `Bearish Breakdown`: Price breaks below key dynamic threshold.
- **Features**: Live text filter, spread percentage tracker, direct CSV export, stock drawer chart launcher.

#### 2.2 HPS Mean Reversion (Institutional Value Zones)
- **Objective**: Identify equities testing key institutional support baselines for high-probability mean-reversion bounces.
- **Institutional Tiers**:
  - **Level-1**: Primary institutional dynamic support.
  - **Level-2**: Intermediate institutional dynamic support.
  - **Level-3**: Macro deep value support baseline.
- **Timeframes**: Daily, Weekly, Monthly.
- **Universes**: NIFTY 500 vs. NIFTY F&O.
- **Proximity Filter**: Equities within +/- 2.0% spread of the target support tier.
- **Status Identifiers**: `At Support Level`, `Testing Level`.
- **Confidentiality Architecture**: Proprietary indicator lengths and mathematical formulas remain strictly confidential to system administrators. Standard users and UI views only see institutional tier abstractions (`Level-1`, `Level-2`, `Level-3`).

#### 2.3 Market Breadth & Sector Heatmaps
- Real-time Advance/Decline ratios across NIFTY 50, NIFTY 500, and Sectoral Indices.
- Sector leadership rankings and breadth distributions.

---

### 3. Telegram Alert Notification System (Hybrid Architecture)

#### 3.1 Distribution Architecture
- **Single Bot Model**: Powered by a central Telegram Bot via the Telegram Bot API (`sendMessage`).
- **Group/Channel Broadcasts**: Automated dispatches to public or private trading groups/channels via chat ID (`-100xxxxxxx`).
- **Private Member DMs**: Individual members can enter their personal Telegram Chat ID in their account profile to receive 1-on-1 direct notifications.

#### 3.2 Alert Payload Schema
All alerts are dispatched in clean HTML format with strict formula confidentiality:
```text
AlphaQuant Screener Alert
Setup: HPS Mean Reversion
Stock: SUNPHARMA (Sun Pharmaceutical Industries Ltd.)
Universe: NIFTY F&O
Timeframe: DAILY
Reversion Tier: Level-2 (At Support Level)
LTP: ₹1,748.00 (+0.30% from level)
Time: 25 Oct 2026, 03:30:00 IST
```

#### 3.3 Admin Configuration Controls
- Enable/Disable dispatcher toggle.
- Bot Token validator with automatic URL/prefix sanitization.
- Broadcast Channel ID mapping.
- Independent event toggles: HPS Breakout alerts and HPS Mean Reversion alerts.
- Live "Send Test Alert" action to verify connectivity.

---

### 4. Data Pipeline & Broker Integration

#### 4.1 Broker Connectivity
- Integrated with **DhanHQ API** for profile discovery, authorizations, and real-time order routing.
- Session storage encrypted at rest using AES-256.

#### 4.2 Multi-Timeframe Historical Engine
- Official NSE market universes:
  - 498 official NIFTY 500 equities.
  - 213 active NIFTY F&O equities.
- High-performance caching layers (`hps_screener_cache.json` and `hps_mean_reversion_cache.json`) for sub-second UI queries and instant tabular rendering.

---

### 5. Export & Reporting
- Standardized CSV export functionality on all screeners:
  - Preserves active search, timeframe, universe, and level filters.
  - Outputs ISO-formatted filenames: `HPS_Mean_Reversion_<universe>_<timeframe>_<level>_<YYYY-MM-DD>.csv`.

---

### 6. Role-Based Access Control (RBAC)
- **Admin**: Full access to Screener Rule builders, User Management, Broker Connection, Telegram Control Center, and confidential indicator settings.
- **Viewer / Trader**: Access to Market Breadth, HPS Stocks, HPS Mean Reversion, CSV Exports, and personal Profile settings.
