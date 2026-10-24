import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.models.entities import User, ScreenerRule, TelegramSettings
from app.api import auth, users, screener, profile, telegram

# Initialize Database tables
Base.metadata.create_all(bind=engine)

def seed_initial_data():
    db = SessionLocal()
    try:
        # Seed Default Admin if not exists
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email="admin@alphaquant.in",
                hashed_password=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                role="admin",
                is_active=True
            )
            db.add(admin)

        # Seed Default Viewer
        viewer = db.query(User).filter(User.username == "viewer").first()
        if not viewer:
            viewer = User(
                username="viewer",
                email="trader@alphaquant.in",
                hashed_password=get_password_hash("Viewer@12345"),
                role="viewer",
                is_active=True
            )
            db.add(viewer)

        # Seed Default Screener Rules if table empty
        rule_count = db.query(ScreenerRule).count()
        if rule_count == 0:
            rules = [
                ScreenerRule(
                    name="High Volume Breakout",
                    description="Stocks gaining over 1.0% with at least 1.5x volume surge",
                    universe="NIFTY50",
                    is_active=True,
                    criteria={
                        "min_price": 50,
                        "min_change_pct": 1.0,
                        "min_volume_ratio": 1.5,
                        "moving_average": "ABOVE_SMA20"
                    }
                ),
                ScreenerRule(
                    name="RSI Momentum Bullish",
                    description="Stocks trading above 50 RSI with positive day price action",
                    universe="NIFTY50",
                    is_active=True,
                    criteria={
                        "min_price": 100,
                        "rsi_min": 55.0,
                        "rsi_max": 75.0,
                        "min_change_pct": 0.5
                    }
                ),
                ScreenerRule(
                    name="Banking Outperformers",
                    description="Banking stocks trading above 50 EMA with strong volume",
                    universe="BANKNIFTY",
                    is_active=True,
                    criteria={
                        "min_price": 100,
                        "min_volume_ratio": 1.2,
                        "moving_average": "ABOVE_EMA50"
                    }
                )
            ]
            db.add_all(rules)

        db.commit()
    finally:
        db.close()

seed_initial_data()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-Grade Indian Stock Market Screener integrated with Dhan API",
    version="1.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["User Management"])
app.include_router(screener.router, prefix="/api/v1/screener", tags=["Screener Engine"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["Dhan Profile"])
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["Telegram Alerts"])

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}

# Mount static web frontend if built
dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.exists(dist_dir):
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        
    @app.get("/")
    def serve_react_root():
        return FileResponse(os.path.join(dist_dir, "index.html"))

    @app.get("/{full_path:path}")
    def serve_react_app(full_path: str):
        file_path = os.path.join(dist_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(dist_dir, "index.html"))
