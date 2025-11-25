import requests
import hmac
import hashlib
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

class Trade:
    def __init__(self, wallet_address: str, market_id: str, outcome_id: str, 
                 side: str, size: float, price: float, timestamp: datetime, trade_hash: str):
        self.wallet_address = wallet_address
        self.market_id = market_id
        self.outcome_id = outcome_id
        self.side = side
        self.size = size
        self.price = price
        self.timestamp = timestamp
        self.trade_hash = trade_hash

class SimpleCopyTrader:
    def __init__(self):
        print("🤖 Initializing CopyTrader...")
        # Initialize config from environment variables
        self.config = self.load_config()
        
        # Get API credentials from environment
        self.api_key = os.getenv('POLYMARKET_API_KEY', '')
        self.api_secret = os.getenv('POLYMARKET_API_SECRET', '')
        self.passphrase = os.getenv('POLYMARKET_PASSPHRASE', '')
        self.dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        
        self.base_url = "https://clob.polymarket.com"
        if self.dry_run:
            self.base_url = "https://clob-staging.polymarket.com"
            print("🚧 DRY RUN MODE - Using staging environment")
        else:
            print("🚀 LIVE TRADING MODE - Using production environment")
    
    def load_config(self):
        """Load configuration from environment variables"""
        print("📁 Loading config from environment...")
        
        # Get wallets from environment variable
        wallets_json = os.getenv('WALLETS', '{}')
        try:
            wallets = json.loads(wallets_json)
            print(f"✅ Loaded {len(wallets)} wallets from environment")
        except:
            wallets = {}
            print("🆕 No wallets in environment - starting fresh")
        
        config = {
            'bot_active': os.getenv('BOT_ACTIVE', 'false').lower() == 'true',
            'test_mode': os.getenv('TEST_MODE', 'true').lower() == 'true',
            'risk_percentage': int(os.getenv('RISK_PERCENTAGE', '10')),
            'copied_wallets': wallets
        }
        
        return config
    
    def save_config(self, config=None):
        """Save configuration - prints instructions to update environment"""
        if config is None:
            config = self.config
        
        print("💾 CONFIG UPDATED - Manual step required:")
        print("==========================================")
        print("Add this to your Render environment variables:")
        print(f"WALLETS={json.dumps(config['copied_wallets'])}")
        print(f"BOT_ACTIVE={str(config['bot_active']).lower()}")
        print(f"TEST_MODE={str(config['test_mode']).lower()}")
        print(f"RISK_PERCENTAGE={config['risk_percentage']}")
        print("==========================================")
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        message = timestamp + method.upper() + path + body
        return hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, path, body)
        
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'POLYMARKET-API-KEY': self.api_key,
            'POLYMARKET-API-SIGNATURE': signature,
            'POLYMARKET-API-TIMESTAMP': timestamp,
            'POLYMARKET-API-PASSPHRASE': self.passphrase,
        }
    
    def get_wallet_trades(self, wallet_address: str, hours_back: int = 24) -> List[Trade]:
        """Get recent trades for a wallet using Polymarket API"""
        if not self.api_key:
            print("❌ API credentials not configured")
            return []
            
        try:
            # Get orders from Polymarket API
            path = "/orders"
            headers = self._get_headers("GET", path)
            response = requests.get(self.base_url + path, headers=headers, timeout=30)
            response.raise_for_status()
            
            orders = response.json()
            wallet_trades = []
            
            since_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            for order in orders:
                order_owner = order.get('owner', '').lower()
                if order_owner == wallet_address.lower():
                    order_time = datetime.fromisoformat(order['createdAt'].replace('Z', '+00:00'))
                    
                    if (order_time > since_time and 
                        order.get('status') in ['FILLED', 'PARTIALLY_FILLED']):
                        
                        token_id = order.get('tokenId', '')
                        market_id = token_id.split('-')[0] if '-' in token_id else token_id
                        outcome_id = token_id.split('-')[1] if '-' in token_id else '0'
                        
                        trade = Trade(
                            wallet_address=wallet_address,
                            market_id=market_id,
                            outcome_id=outcome_id,
                            side='BUY' if order.get('side') == 'buy' else 'SELL',
                            size=float(order.get('size', 0)),
                            price=float(order.get('price', 0)),
                            timestamp=order_time,
                            trade_hash=order.get('id', '')
                        )
                        wallet_trades.append(trade)
            
            print(f"📊 Found {len(wallet_trades)} recent trades for {wallet_address}")
            return wallet_trades
            
        except Exception as e:
            print(f"❌ Error fetching trades for {wallet_address}: {e}")
            return []
    
    def place_trade(self, trade: Trade, risk_percentage: float) -> bool:
        """Place a copy trade"""
        copy_size = trade.size * (risk_percentage / 100)
        
        if self.dry_run or self.config.get('test_mode', True):
            print(f"🧪 DRY RUN: Would copy {trade.side} {copy_size:.4f} @ {trade.price}")
            return True
        
        try:
            token_id = f"{trade.market_id}-{trade.outcome_id}"
            order_data = {
                "tokenId": token_id,
                "side": trade.side.lower(),
                "size": str(copy_size),
                "price": str(trade.price),
                "nonce": str(int(time.time() * 1000)),
            }
            
            path = "/orders"
            body = json.dumps(order_data)
            headers = self._get_headers("POST", path, body)
            
            response = requests.post(self.base_url + path, headers=headers, json=order_data, timeout=30)
            response.raise_for_status()
            
            print(f"✅ COPIED TRADE: {trade.side} {copy_size:.4f} @ {trade.price}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to place trade: {e}")
            return False
    
    def monitor_and_copy(self):
        """Main monitoring function"""
        if not self.config.get('bot_active', False):
            print("⏸️ Bot is not active - skipping monitoring")
            return
            
        print(f"🔍 Monitoring {len(self.config.get('copied_wallets', {}))} wallets...")
        
        for wallet_address, wallet_data in self.config.get('copied_wallets', {}).items():
            if not isinstance(wallet_data, dict) or not wallet_data.get('active', True):
                continue
                
            nickname = wallet_data.get('nickname', 'Unknown')
            print(f"👀 Checking {nickname} ({wallet_address})...")
            
            recent_trades = self.get_wallet_trades(wallet_address)
            
            for trade in recent_trades:
                risk_percentage = self.config.get('risk_percentage', 10)
                print(f"🆕 New trade: {trade.side} {trade.size} @ {trade.price}")
                
                success = self.place_trade(trade, risk_percentage)
                
                if success:
                    print(f"✅ Copied trade from {nickname}")
                else:
                    print(f"❌ Failed to copy from {nickname}")

    def load_my_positions(self):
        return []

# Create a global bot instance
bot = SimpleCopyTrader()