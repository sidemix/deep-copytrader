from datetime import datetime
from sqlalchemy.orm import Session
from app.models import LeaderWallet, LeaderTrade, FollowerTrade
from app.polymarket_client import PolymarketClient, TradeDTO
from app.risk import RiskManager
import app.config as config

class CopyTrader:
    def __init__(self, db: Session):
        self.db = db
        self.polymarket_client = PolymarketClient()
        self.risk_manager = RiskManager(db)
    
    def process_leader_trades(self):
        """Main method to process new trades from leader wallets"""
        if not self._is_bot_running():
            print("Bot is not running, skipping trade processing")
            return
        
        active_wallets = self.db.query(LeaderWallet).filter(LeaderWallet.active == True).all()
        
        for wallet in active_wallets:
            try:
                self._process_wallet_trades(wallet)
            except Exception as e:
                print(f"Error processing wallet {wallet.nickname}: {e}")
    
    def _process_wallet_trades(self, wallet: LeaderWallet):
        """Process trades for a single wallet"""
        # Get last processed timestamp for this wallet
        last_trade = self.db.query(LeaderTrade).filter(
            LeaderTrade.wallet_address == wallet.wallet_address
        ).order_by(LeaderTrade.timestamp.desc()).first()
        
        since_timestamp = last_trade.timestamp if last_trade else datetime.utcnow().replace(hour=0, minute=0, second=0)
        
        # Fetch new trades
        new_trades = self.polymarket_client.get_trades_for_wallet(
            wallet.wallet_address, since_timestamp
        )
        
        for trade_dto in new_trades:
            # Check if we've already processed this trade
            existing = self.db.query(LeaderTrade).filter(
                LeaderTrade.trade_hash == trade_dto.trade_hash
            ).first()
            
            if not existing:
                self._handle_new_leader_trade(wallet, trade_dto)
    
    def _handle_new_leader_trade(self, wallet: LeaderWallet, trade_dto: TradeDTO):
        """Handle a new trade from a leader wallet"""
        # Store leader trade
        leader_trade = LeaderTrade(
            wallet_address=trade_dto.wallet_address,
            market_id=trade_dto.market_id,
            outcome_id=trade_dto.outcome_id,
            side=trade_dto.side,
            size=trade_dto.size,
            price=trade_dto.price,
            timestamp=trade_dto.timestamp,
            trade_hash=trade_dto.trade_hash
        )
        self.db.add(leader_trade)
        self.db.commit()
        self.db.refresh(leader_trade)
        
        # Calculate copy size
        copy_size = self.risk_manager.calculate_copy_size(
            trade_dto.size, wallet.copy_percentage
        )
        
        # Check risk limits
        can_trade, reason = self.risk_manager.can_open_trade(
            wallet.wallet_address,
            trade_dto.market_id,
            trade_dto.outcome_id,
            trade_dto.side,
            copy_size,
            trade_dto.price
        )
        
        # Create follower trade record
        follower_trade = FollowerTrade(
            leader_trade_id=leader_trade.id,
            market_id=trade_dto.market_id,
            outcome_id=trade_dto.outcome_id,
            side=trade_dto.side,
            size=copy_size,
            price=trade_dto.price,
            is_dry_run=config.is_test_mode
        )
        
        if can_trade:
            # Place the order
            order_result = self.polymarket_client.place_order(
                trade_dto.market_id,
                trade_dto.outcome_id,
                trade_dto.side,
                copy_size,
                trade_dto.price
            )
            
            if order_result.success:
                follower_trade.status = "EXECUTED"
                print(f"SUCCESS: Copied trade from {wallet.nickname} - {trade_dto.side} {copy_size} @ {trade_dto.price}")
            else:
                follower_trade.status = "REJECTED"
                follower_trade.rejection_reason = order_result.error
                print(f"ORDER FAILED: {order_result.error}")
        else:
            follower_trade.status = "REJECTED"
            follower_trade.rejection_reason = reason
            print(f"RISK REJECTED: {reason}")
        
        self.db.add(follower_trade)
        self.db.commit()
    
    def _is_bot_running(self) -> bool:
        """Check if bot is running globally"""
        # You might want to store this in a proper settings table
        # For now, we'll assume it's always running when called
        return True