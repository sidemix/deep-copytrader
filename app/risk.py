from typing import Tuple, Dict
from sqlalchemy.orm import Session
import app.config as config
from app.models import FollowerTrade, LeaderWallet

class RiskManager:
    def __init__(self, db: Session):
        self.db = db
        self.max_trade_size = config.MAX_TRADE_SIZE
        self.max_wallet_exposure = config.MAX_WALLET_EXPOSURE
    
    def can_open_trade(self, wallet_address: str, market_id: str, outcome_id: str, 
                      side: str, size: float, price: float) -> Tuple[bool, str]:
        """
        Check if a trade can be opened based on risk rules.
        Returns (can_trade, reason)
        """
        
        # 1. Check max trade size
        notional = size * price
        if notional > self.max_trade_size:
            return False, f"Trade size ${notional:.2f} exceeds max ${self.max_trade_size:.2f}"
        
        # 2. Check wallet exposure
        wallet_exposure = self._get_wallet_exposure(wallet_address)
        if wallet_exposure + notional > self.max_wallet_exposure:
            return False, f"Wallet exposure ${wallet_exposure + notional:.2f} exceeds max ${self.max_wallet_exposure:.2f}"
        
        # 3. Check for duplicate active positions
        if self._has_duplicate_position(wallet_address, market_id, outcome_id, side):
            return False, "Duplicate active position detected"
        
        return True, "OK"
    
    def _get_wallet_exposure(self, wallet_address: str) -> float:
        """Calculate current exposure for a wallet"""
        # Get all active trades for this wallet
        active_trades = self.db.query(FollowerTrade).filter(
            FollowerTrade.status == "EXECUTED"
        ).all()
        
        exposure = 0.0
        for trade in active_trades:
            exposure += trade.size * trade.price
        
        return exposure
    
    def _has_duplicate_position(self, wallet_address: str, market_id: str, 
                               outcome_id: str, side: str) -> bool:
        """Check if similar position already exists"""
        existing = self.db.query(FollowerTrade).filter(
            FollowerTrade.market_id == market_id,
            FollowerTrade.outcome_id == outcome_id,
            FollowerTrade.side == side,
            FollowerTrade.status == "EXECUTED"
        ).first()
        
        return existing is not None
    
    def calculate_copy_size(self, leader_size: float, copy_percentage: float) -> float:
        """Calculate the size to copy based on percentage"""
        return leader_size * copy_percentage