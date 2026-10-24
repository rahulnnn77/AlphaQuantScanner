# AlphaQuant - Indian Stock Market Screener Web Application

A production-grade Indian Stock Market Screener Web Application built using **FastAPI (Python)** and **React 18 + Tailwind CSS (Vite)** with native **Dhan (DhanHQ) API/SDK** integration.

---

## Key Highlights & Architecture

- **Role-Based Access Control**:
  - **Admin**: Manages Dhan broker connection, manages user credentials (grant/revoke access), creates and edits quantitative screener rules.
  - **Viewer/Trader**: Views live stock screener results, price quotes, indicators (RSI, SMA/EMA, Volume Surge), and broker account products with zero broker credential exposure.
- **Security & Token Persistence**:
  - Broker secrets and session tokens are **never** returned or stored on the browser.
  - Dhan session is stored securely using AES/Fernet encryption on the backend (`backend/data/.session.json`), persisting across hot reloads and server restarts.
- **DhanHQ Integration**:
  - Automatic session status monitoring (`/api/v1/auth/session-status`).
  - Real-time Indian market trading hour detection (NSE/BSE IST time check).
  - Profile inspection displaying Active Products (CNC, INTRADAY, MARGIN, MTF) and Enabled Exchanges (NSE, BSE, NFO).
- **Dark-Themed Financial UI**:
  - Styled with Tailwind CSS (`#0B0F19` background, `#111827` surface cards, `#1F2937` borders).
  - Designed for high-frequency market readability with color-coded gainers/losers, volume surges, and RSI status badges.

---

## Project Structure

```
AlphaQuantScanner/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py          # App login, Dhan broker login, and session status
│   │   │   ├── deps.py          # JWT authentication and admin role enforcement
│   │   │   ├── profile.py       # Dhan broker account profile & products
│   │   │   ├── screener.py      # Live scan results & admin rule configurations
│   │   │   └── users.py         # User management (add/deactivate/delete)
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic environment configuration
│   │   │   ├── database.py      # SQLAlchemy SQLite/PostgreSQL setup
│   │   │   ├── security.py      # Password hashing & JWT token generators
│   │   │   └── session_store.py # AES/Fernet encrypted Dhan token storage
│   │   ├── models/
│   │   │   └── entities.py      # User, ScreenerRule, and Access entities
│   │   ├── schemas/
│   │   │   └── schemas.py       # Pydantic schemas for requests & responses
│   │   └── services/
│   │       ├── dhan_service.py  # DhanHQ official SDK integration
│   │       └── screener_engine.py # Technical indicators & screening evaluation
│   ├── data/                    # Persistent SQLite database & encrypted session
│   ├── requirements.txt         # Python dependencies
│   └── main.py                  # FastAPI application entrypoint
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── Layout.jsx       # Responsive navigation & real-time status bar
│   │   ├── context/
│   │   │   └── AuthContext.jsx  # React Context for auth & broker health
│   │   ├── pages/
│   │   │   ├── AdminBrokerAuth.jsx    # Dhan API Key / Token input
│   │   │   ├── AdminScreenerConfig.jsx# Custom rule editor & indicator toggles
│   │   │   ├── AdminUsers.jsx         # User accounts & role manager
│   │   │   ├── Dashboard.jsx          # Live stock screener table
│   │   │   ├── Login.jsx              # System login with demo shortcuts
│   │   │   └── Profile.jsx            # Account details & products
│   │   ├── api.js               # Axios instance with auth interceptor
│   │   ├── App.jsx              # React Router setup & protected routes
│   │   ├── index.css            # Tailwind directives & dark theme tokens
│   │   └── main.jsx             # React DOM entry
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.js
│   └── index.html
├── .env.example
├── .env
└── README.md
```

---

## Step-by-Step Setup & Run Instructions

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+ & npm**

### 2. Backend Setup
1. Open a terminal in the root directory:
   ```bash
   cd backend
   ```
2. (Optional) Create and activate a Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI backend server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   The backend API will be available at `http://localhost:8000`.
   Interactive Swagger documentation is at `http://localhost:8000/docs`.

### 3. Frontend Setup
1. Open a second terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install frontend packages:
   ```bash
   npm install
   ```
3. Launch the Vite development server:
   ```bash
   npm run dev
   ```
   The web application will open at `http://localhost:5173`.

---

## Default Access Credentials

| Role | Username | Password | Notes |
|---|---|---|---|
| **Admin** | `admin` | `Admin@12345` | Can configure broker authentication, rules, and users |
| **Viewer** | `viewer` | `Viewer@12345` | Read-only view for screener and profile |

---

## Dhan Broker Authentication Flow

1. Log in as **Admin** and navigate to **Dhan Broker Auth** (`/admin/broker-auth`).
2. Input your:
   - **Dhan Client ID / API Key**: 10-digit Dhan registered Client ID.
   - **API Secret**: (Optional if direct access token is provided).
   - **Request Token / Access Token**: Paste the generated access token or consent token ID.
3. Click **"Connect Broker & Login"**.
4. The backend verifies the token with Dhan HQ, retrieves account details, and securely encrypts it to `backend/data/.session.json`.
5. The session will automatically persist across server reboots.
