from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import json

from app.models import get_db, LeaderWallet, FollowerTrade, LeaderTrade
from app.monitor import MonitoringService
import app.config as config

app = FastAPI(title="Polymarket Copytrader")
templates = Jinja2Templates(directory="app/templates")

# Global monitoring service
monitoring_service = None

@app.on_event("startup")
async def startup_event():
    global monitoring_service
    db = next(get_db())
    monitoring_service = MonitoringService(db)
    monitoring_service.start()

@app.on_event("shutdown")
async def shutdown_event():
    global monitoring_service
    if monitoring_service:
        monitoring_service.stop()

@app.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    # Get all wallets with stats
    wallets = db.query(LeaderWallet).all()
    
    # Calculate stats for each wallet
    for wallet in wallets:
        wallet.stats = get_wallet_stats(db, wallet.id)
    
    # Get overall stats
    total_stats = get_total_stats(db)
    
    # Get recent activity
    recent_activity = get_recent_activity(db)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "wallets": wallets,
        "stats": total_stats,
        "recent_activity": recent_activity,
        "config": config
    })

@app.get("/wallets/add")
async def add_wallet_form(request: Request):
    return templates.TemplateResponse("wallets_add.html", {
        "request": request,
        "default_percentage": config.DEFAULT_COPY_PERCENTAGE
    })

@app.post("/wallets/add")
async def add_wallet(
    request: Request,
    nickname: str = Form(...),
    wallet_address: str = Form(...),
    copy_percentage: float = Form(...),
    db: Session = Depends(get_db)
):
    # Validate wallet address format
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address format")
    
    # Check if wallet already exists
    existing = db.query(LeaderWallet).filter(LeaderWallet.wallet_address == wallet_address).first()
    if existing:
        raise HTTPException(status_code=400, detail="Wallet already exists")
    
    # Create new wallet
    wallet = LeaderWallet(
        nickname=nickname,
        wallet_address=wallet_address,
        copy_percentage=copy_percentage,
        active=True
    )
    
    db.add(wallet)
    db.commit()
    
    return RedirectResponse("/", status_code=303)

@app.get("/wallets/{wallet_id}/toggle")
async def toggle_wallet(wallet_id: int, db: Session = Depends(get_db)):
    wallet = db.query(LeaderWallet).filter(LeaderWallet.id == wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    wallet.active = not wallet.active
    db.commit()
    
    return RedirectResponse("/", status_code=303)

def get_wallet_stats(db: Session, wallet_id: int):
    """Calculate statistics for a wallet"""
    trades = db.query(FollowerTrade).join(LeaderTrade).filter(
        LeaderTrade.wallet_address == db.query(LeaderWallet.wallet_address).filter(LeaderWallet.id == wallet_id).scalar_subquery()
    ).all()
    
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": 0,
            "pnl": 0
        }
    
    # Simplified P&L calculation - you'll want to implement proper P&L logic
    # based on market resolution and actual trade outcomes
    winning_trades = len([t for t in trades if t.price > 0.5])  # Simplified
    
    return {
        "trade_count": len(trades),
        "win_rate": winning_trades / len(trades) if trades else 0,
        "pnl": sum(t.size * (t.price - 0.5) for t in trades)  # Simplified P&L
    }

def get_total_stats(db: Session):
    """Calculate total statistics"""
    wallets = db.query(LeaderWallet).all()
    all_trades = db.query(FollowerTrade).all()
    
    wallet_stats = [get_wallet_stats(db, wallet.id) for wallet in wallets]
    
    return {
        "total_wallets": len(wallets),
        "active_wallets": len([w for w in wallets if w.active]),
        "total_copied_trades": len(all_trades),
        "total_pnl": sum(stats["pnl"] for stats in wallet_stats)
    }

def get_recent_activity(db: Session, limit: int = 10):
    """Get recent follower trade activity"""
    recent_trades = db.query(FollowerTrade).order_by(
        FollowerTrade.executed_at.desc()
    ).limit(limit).all()
    
    activity = []
    for trade in recent_trades:
        # Get wallet nickname
        leader_trade = db.query(LeaderTrade).filter(LeaderTrade.id == trade.leader_trade_id).first()
        wallet = db.query(LeaderWallet).filter(LeaderWallet.wallet_address == leader_trade.wallet_address).first() if leader_trade else None
        
        activity.append({
            "executed_at": trade.executed_at,
            "wallet_nickname": wallet.nickname if wallet else "Unknown",
            "side": trade.side,
            "market_id": trade.market_id,
            "size": trade.size,
            "price": trade.price,
            "status": trade.status
        })
    
    return activity