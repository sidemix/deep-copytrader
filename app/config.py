import os
from dotenv import load_dotenv

load_dotenv()



class Config:
    # Polymarket API
    POLYMARKET_API_KEY = os.getenv("POLYMARKET_API_KEY", "")
    POLYMARKET_API_SECRET = os.getenv("POLYMARKET_API_SECRET", "")
    POLYMARKET_PASSPHRASE = os.getenv("POLYMARKET_PASSPHRASE", "")
    
    # App Settings
    MODE = os.getenv("MODE", "TEST")
    DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "30"))
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./copytrader.db")
    
    # Risk Management
    DEFAULT_COPY_PERCENTAGE = float(os.getenv("DEFAULT_COPY_PERCENTAGE", "0.1"))
    MAX_TRADE_SIZE = float(os.getenv("MAX_TRADE_SIZE", "1000"))
    MAX_WALLET_EXPOSURE = float(os.getenv("MAX_WALLET_EXPOSURE", "5000"))
    
# In Config class, add:
@property
def database_url(self):
    # Use PostgreSQL if available, otherwise SQLite
    if 'DATABASE_URL' in os.environ and os.environ['DATABASE_URL'].startswith('postgres'):
        return os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://')
    return self.DATABASE_URL

config = Config()