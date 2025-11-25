from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import app.config as config

engine = create_engine(config.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class LeaderWallet(Base):
    __tablename__ = "leader_wallets"
    
    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String, nullable=False)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    active = Column(Boolean, default=True)
    copy_percentage = Column(Float, default=0.1)  # 10% by default
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<LeaderWallet {self.nickname} ({self.wallet_address})>"

class LeaderTrade(Base):
    __tablename__ = "leader_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, index=True, nullable=False)
    market_id = Column(String, nullable=False)
    outcome_id = Column(String, nullable=False)
    side = Column(String, nullable=False)  # BUY or SELL
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    trade_hash = Column(String, unique=True, nullable=False)  # For deduplication
    
    def __repr__(self):
        return f"<LeaderTrade {self.side} {self.size}@{self.price}>"

class FollowerTrade(Base):
    __tablename__ = "follower_trades"
    
    id = Column(Integer, primary_key=True, index=True)
    leader_trade_id = Column(Integer, index=True)
    market_id = Column(String, nullable=False)
    outcome_id = Column(String, nullable=False)
    side = Column(String, nullable=False)
    size = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(String, default="EXECUTED")  # EXECUTED, REJECTED, PENDING
    rejection_reason = Column(Text)
    is_dry_run = Column(Boolean, default=False)
    executed_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<FollowerTrade {self.side} {self.size}@{self.price}>"

class BotStatus:
    __tablename__ = "bot_status"
    
    id = Column(Integer, primary_key=True, index=True)
    running = Column(Boolean, default=False)
    last_check = Column(DateTime)
    
    def __repr__(self):
        return f"<BotStatus running={self.running}>"

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()