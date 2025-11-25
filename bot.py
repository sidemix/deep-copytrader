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
        # Initialize config FIRST
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
    """Load configuration from JSON file - uses persistent storage if available"""
    # Try persistent disk first, then fallback to local
    config_paths = ['/opt/data/config.json', 'config.json']
    
    for config_path in config_paths:
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Ensure copied_wallets exists
                if 'copied_wallets' not in config:
                    config['copied_wallets'] = {}
                print(f"✅ Loaded config from {config_path}")
                return config
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"⚠️ Error loading {config_path}: {e}")
            continue
    
    # Create default config if no file exists
    print("🆕 Creating new config file")
    default_config = {
        'bot_active': False,
        'test_mode': True,
        'risk_percentage': 10,
        'copied_wallets': {}
    }
    self.save_config(default_config)
    return default_config

def save_config(self, config=None):
    """Save configuration to JSON file - uses persistent storage if available"""
    if config is None:
        config = self.config
    
    # Try persistent disk first, then fallback to local
    config_paths = ['/opt/data/config.json', 'config.json']
    saved = False
    
    for config_path in config_paths:
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"💾 Saved config to {config_path}")
            saved = True
            break
        except Exception as e:
            print(f"⚠️ Could not save to {config_path}: {e}")
            continue
    
    if not saved:
        print("❌ Failed to save config to any location")
    
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
                    
                    # Only process filled orders within our time range
                    if (order_time > since_time and 
                        order.get('status') in ['FILLED', 'PARTIALLY_FILLED']):
                        
                        # Parse token ID to get market and outcome
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
        copy_size = trade.size * (risk_percentage / 100)  # Convert percentage to decimal
        
        if self.dry_run or self.config.get('test_mode', True):
            print(f"🧪 DRY RUN: Would copy {trade.side} {copy_size:.4f} @ {trade.price} for {trade.market_id}")
            
            # Update wallet stats
            wallet_data = self.config['copied_wallets'].get(trade.wallet_address, {})
            if isinstance(wallet_data, dict):
                wallet_data['total_trades'] = wallet_data.get('total_trades', 0) + 1
                # Simple P&L simulation
                wallet_data['total_pnl'] = wallet_data.get('total_pnl', 0) + (copy_size * 0.1)  # Simulate profit
                wallet_data['profitable_trades'] = wallet_data.get('profitable_trades', 0) + 1
                self.config['copied_wallets'][trade.wallet_address] = wallet_data
                self.save_config()
            
            return True
        
        try:
            # Place real order
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
            
            result = response.json()
            print(f"✅ COPIED TRADE: {trade.side} {copy_size:.4f} @ {trade.price}")
            
            # Update wallet stats for real trade
            wallet_data = self.config['copied_wallets'].get(trade.wallet_address, {})
            if isinstance(wallet_data, dict):
                wallet_data['total_trades'] = wallet_data.get('total_trades', 0) + 1
                self.config['copied_wallets'][trade.wallet_address] = wallet_data
                self.save_config()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to place trade: {e}")
            return False
    
    def monitor_and_copy(self):
        """Main monitoring function - check all active wallets and copy trades"""
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
                # In a real implementation, you'd check if we already copied this trade
                # For now, we'll copy all new trades
                risk_percentage = self.config.get('risk_percentage', 10)
                print(f"🆕 New trade detected: {trade.side} {trade.size} @ {trade.price}")
                
                success = self.place_trade(trade, risk_percentage)
                
                if success:
                    print(f"✅ Successfully copied trade from {nickname}")
                else:
                    print(f"❌ Failed to copy trade from {nickname}")
    
    def run_continuous(self, interval_minutes: int = 5):
        """Run the bot continuously"""
        print(f"🤖 Starting copy trader bot (checking every {interval_minutes} minutes)")
        print(f"📊 Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        
        while True:
            try:
                self.monitor_and_copy()
                print(f"💤 Waiting {interval_minutes} minutes until next check...")
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print("🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

# Create a global bot instance
bot = SimpleCopyTrader()

# For manual testing
if __name__ == "__main__":
    # Run once
    bot.monitor_and_copy()
    
    # Or run continuously (uncomment next line)
    # bot.run_continuous(interval_minutes=5)