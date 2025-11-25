from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.models import get_db, LeaderWallet, FollowerTrade, LeaderTrade
import app.config as config

app = FastAPI(title="Polymarket Copytrader")
templates = Jinja2Templates(directory="app/templates")

# Simple in-memory monitoring control
monitoring_active = True

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        # Get all wallets with stats
        wallets = db.query(LeaderWallet).all()
        
        # Calculate stats for each wallet
        for wallet in wallets:
            wallet.stats = get_wallet_stats(db, wallet.id)
        
        # Get overall stats
        total_stats = get_total_stats(db, wallets)
        
        # Get recent activity
        recent_activity = get_recent_activity(db)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "wallets": wallets,
            "stats": total_stats,
            "recent_activity": recent_activity,
            "config": config,
            "monitoring_active": monitoring_active
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })

@app.get("/wallets/add", response_class=HTMLResponse)
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
    wallet_address = wallet_address.strip()
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address format. Must be 42 characters starting with 0x")
    
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

@app.get("/bot/toggle")
async def toggle_bot():
    global monitoring_active
    monitoring_active = not monitoring_active
    return RedirectResponse("/", status_code=303)

def get_wallet_stats(db: Session, wallet_id: int):
    """Calculate statistics for a wallet"""
    wallet = db.query(LeaderWallet).filter(LeaderWallet.id == wallet_id).first()
    if not wallet:
        return {"trade_count": 0, "win_rate": 0, "pnl": 0}
    
    trades = db.query(FollowerTrade).join(LeaderTrade).filter(
        LeaderTrade.wallet_address == wallet.wallet_address
    ).all()
    
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": 0,
            "pnl": 0
        }
    
    # Simplified P&L calculation
    winning_trades = len([t for t in trades if t.price > 0.5])  # Simplified logic
    
    return {
        "trade_count": len(trades),
        "win_rate": winning_trades / len(trades) if trades else 0,
        "pnl": sum(t.size * (t.price - 0.5) for t in trades)  # Simplified P&L
    }

def get_total_stats(db: Session, wallets: list):
    """Calculate total statistics"""
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
        if leader_trade:
            wallet = db.query(LeaderWallet).filter(LeaderWallet.wallet_address == leader_trade.wallet_address).first()
            wallet_nickname = wallet.nickname if wallet else "Unknown"
        else:
            wallet_nickname = "Unknown"
        
        activity.append({
            "executed_at": trade.executed_at,
            "wallet_nickname": wallet_nickname,
            "side": trade.side,
            "market_id": trade.market_id[:8] + "..." if trade.market_id else "Unknown",
            "size": trade.size,
            "price": trade.price,
            "status": trade.status
        })
    
    return activity