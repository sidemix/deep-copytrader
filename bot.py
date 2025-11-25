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
        """Load configuration with robust disk handling"""
        print("📁 Loading config...")
        
        persistent_path = '/opt/data/config.json'
        local_path = 'config.json'
        
        # Strategy: Try multiple approaches
        config_attempts = []
        
        # Attempt 1: Persistent disk
        try:
            if os.path.exists(persistent_path):
                with open(persistent_path, 'r') as f:
                    config = json.load(f)
                    if 'copied_wallets' not in config:
                        config['copied_wallets'] = {}
                    config_attempts.append(('persistent', config, len(config.get('copied_wallets', {}))))
                    print(f"✅ Found persistent config with {len(config.get('copied_wallets', {}))} wallets")
            else:
                print("📭 No config found on persistent disk")
        except Exception as e:
            print(f"⚠️ Error reading persistent: {e}")
        
        # Attempt 2: Local file
        try:
            if os.path.exists(local_path):
                with open(local_path, 'r') as f:
                    config = json.load(f)
                    if 'copied_wallets' not in config:
                        config['copied_wallets'] = {}
                    config_attempts.append(('local', config, len(config.get('copied_wallets', {}))))
                    print(f"✅ Found local config with {len(config.get('copied_wallets', {}))} wallets")
            else:
                print("📭 No config found locally")
        except Exception as e:
            print(f"⚠️ Error reading local: {e}")
        
        # Choose the best config (prefer one with most wallets)
        if config_attempts:
            # Sort by wallet count (descending) and then prefer persistent
            config_attempts.sort(key=lambda x: (-x[2], x[0] != 'persistent'))
            best_source, best_config, wallet_count = config_attempts[0]
            print(f"🎯 Using config from {best_source} with {wallet_count} wallets")
            
            # If we're using local but persistent exists or we can write to persistent, sync them
            if best_source == 'local' and os.path.exists('/opt/data'):
                try:
                    with open(persistent_path, 'w') as f:
                        json.dump(best_config, f, indent=2)
                    print(f"💾 Synced local config to persistent disk")
                except Exception as e:
                    print(f"⚠️ Could not sync to persistent: {e}")
            
            return best_config
        
        # No config found anywhere - create new
        print("🆕 Creating new config...")
        default_config = {
            'bot_active': False,
            'test_mode': True,
            'risk_percentage': 10,
            'copied_wallets': {}
        }
        
        # Try to create on persistent disk first
        created = False
        if os.path.exists('/opt/data'):
            try:
                with open(persistent_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                print(f"💾 Created new config on persistent disk")
                created = True
            except Exception as e:
                print(f"⚠️ Could not create on persistent: {e}")
        
        # Fallback to local
        if not created:
            try:
                with open(local_path, 'w') as f:
                    json.dump(default_config, f, indent=2)
                print(f"💾 Created new config locally")
            except Exception as e:
                print(f"❌ Failed to create config anywhere: {e}")
        
        return default_config
    
    def save_config(self, config=None):
        """Save configuration with robust error handling"""
        if config is None:
            config = self.config
        
        print(f"💾 Attempting to save {len(config.get('copied_wallets', {}))} wallets...")
        
        saved_locations = []
        
        # Try persistent disk first
        persistent_path = '/opt/data/config.json'
        if os.path.exists('/opt/data'):
            try:
                os.makedirs('/opt/data', exist_ok=True)
                with open(persistent_path, 'w') as f:
                    json.dump(config, f, indent=2)
                saved_locations.append('persistent')
                print(f"✅ Saved to persistent disk")
            except Exception as e:
                print(f"❌ Failed to save to persistent: {e}")
        
        # Always try local as backup
        local_path = 'config.json'
        try:
            with open(local_path, 'w') as f:
                json.dump(config, f, indent=2)
            saved_locations.append('local')
            print(f"✅ Saved locally")
        except Exception as e:
            print(f"❌ Failed to save locally: {e}")
        
        if not saved_locations:
            print("🚨 CRITICAL: Could not save config anywhere!")
        else:
            print(f"🎉 Successfully saved to: {', '.join(saved_locations)}")
    
    def log_activity(self, message, wallet_address=None, trade_data=None):
        """Log activity for dashboard viewing"""
        activity = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'wallet': wallet_address,
            'trade_data': trade_data
        }
        
        # Load existing activity log
        activity_log = self.load_activity_log()
        activity_log.append(activity)
        
        # Keep only last 100 activities
        if len(activity_log) > 100:
            activity_log = activity_log[-100:]
        
        # Save to persistent disk
        self.save_activity_log(activity_log)

    def load_activity_log(self):
        """Load activity log from disk"""
        try:
            with open('/opt/data/activity_log.json', 'r') as f:
                return json.load(f)
        except:
            return []

    def save_activity_log(self, activity_log):
        """Save activity log to disk"""
        try:
            with open('/opt/data/activity_log.json', 'w') as f:
                json.dump(activity_log, f, indent=2)
        except Exception as e:
            print(f"⚠️ Could not save activity log: {e}")

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
    
    def get_wallet_trades(self, wallet_address: str, minutes_back: int = 2) -> List[Trade]:
        """Get VERY recent trades (last 2 minutes instead of 24 hours)"""
        if not self.api_key:
            print("❌ API credentials not configured")
            return []
            
        try:
            # Get orders from Polymarket API
            path = "/orders"
            headers = self._get_headers("GET", path)
            response = requests.get(self.base_url + path, headers=headers, timeout=10)  # Faster timeout
            response.raise_for_status()
            
            orders = response.json()
            wallet_trades = []
            
            # Check only last 2 minutes for maximum freshness
            since_time = datetime.utcnow() - timedelta(minutes=minutes_back)
            
            for order in orders:
                order_owner = order.get('owner', '').lower()
                if order_owner == wallet_address.lower():
                    order_time = datetime.fromisoformat(order['createdAt'].replace('Z', '+00:00'))
                    
                    # Only process VERY recent filled orders
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
            
            # Sort by most recent first
            wallet_trades.sort(key=lambda x: x.timestamp, reverse=True)
            
            if wallet_trades:
                latest_trade_time = wallet_trades[0].timestamp
                delay = (datetime.utcnow() - latest_trade_time).total_seconds()
                print(f"📊 Found {len(wallet_trades)} trades in last {minutes_back}min for {wallet_address}")
                print(f"⏱️  Latest trade was {delay:.1f} seconds ago")
            else:
                print(f"📭 No recent trades found for {wallet_address}")
                
            return wallet_trades
            
        except Exception as e:
            print(f"❌ Error fetching trades for {wallet_address}: {e}")
            return []
    
    def place_trade(self, trade: Trade, risk_percentage: float) -> bool:
        """Place a copy trade"""
        copy_size = trade.size * (risk_percentage / 100)  # Convert percentage to decimal
        
        if self.dry_run or self.config.get('test_mode', True):
            print(f"🧪 DRY RUN: Would copy {trade.side} {copy_size:.4f} @ {trade.price} for {trade.market_id}")
            self.log_activity(f"🧪 DRY RUN: Would copy {trade.side} {copy_size:.4f} @ {trade.price}")
            
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
            self.log_activity(f"✅ COPIED TRADE: {trade.side} {copy_size:.4f} @ {trade.price}")
            
            # Update wallet stats for real trade
            wallet_data = self.config['copied_wallets'].get(trade.wallet_address, {})
            if isinstance(wallet_data, dict):
                wallet_data['total_trades'] = wallet_data.get('total_trades', 0) + 1
                self.config['copied_wallets'][trade.wallet_address] = wallet_data
                self.save_config()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to place trade: {e}")
            self.log_activity(f"❌ Failed to place trade: {e}")
            return False
    
    def monitor_and_copy(self):
        """Main monitoring function - optimized for speed"""
        self.log_activity("🤖 Bot monitoring started")
        
        if not self.config.get('bot_active', False):
            self.log_activity("⏸️ Bot is not active - skipping monitoring")
            print("⏸️ Bot is not active - skipping monitoring")
            return

        active_wallets = [addr for addr, data in self.config.get('copied_wallets', {}).items() 
                         if isinstance(data, dict) and data.get('active', True)]
        
        print(f"🔍 Monitoring {len(active_wallets)} active wallets...")
        
        for wallet_address in active_wallets:
            wallet_data = self.config['copied_wallets'][wallet_address]
            nickname = wallet_data.get('nickname', 'Unknown')
            print(f"👀 Checking {nickname} ({wallet_address})...")
            
            # Get VERY recent trades (last 2 minutes)
            recent_trades = self.get_wallet_trades(wallet_address, minutes_back=2)
            
            for trade in recent_trades:
                # Calculate how old this trade is
                trade_age = (datetime.utcnow() - trade.timestamp).total_seconds()
                
                self.log_activity(
                    f"🆕 New trade detected: {trade.side} {trade.size} @ {trade.price} ({trade_age:.1f}s ago)",
                    wallet_address=wallet_address,
                    trade_data={'side': trade.side, 'size': trade.size, 'price': trade.price, 'age_seconds': trade_age}
                )
                
                risk_percentage = self.config.get('risk_percentage', 10)
                print(f"🆕 Trade detected {trade_age:.1f}s ago: {trade.side} {trade.size} @ {trade.price}")
                
                # Only copy if trade is reasonably fresh (under 2 minutes old)
                if trade_age < 120:  # 2 minutes
                    success = self.place_trade(trade, risk_percentage)
                    
                    if success:
                        self.log_activity(f"✅ Copied trade from {nickname} ({trade_age:.1f}s delay)", wallet_address=wallet_address)
                        print(f"✅ Successfully copied trade from {nickname} ({trade_age:.1f}s delay)")
                    else:
                        self.log_activity(f"❌ Failed to copy from {nickname}", wallet_address=wallet_address)
                        print(f"❌ Failed to copy trade from {nickname}")
                else:
                    print(f"⏰ Trade too old ({trade_age:.1f}s), skipping")
        
        self.log_activity("✅ Bot monitoring completed")
    
    def run_continuous(self, interval_seconds: int = 15):
        """Run the bot continuously with 15-second checks"""
        print(f"🤖 Starting copy trader bot (checking every {interval_seconds} seconds)")
        print(f"📊 Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        print(f"🎯 Target: ~15-30 second delay after leader trades")
        
        check_count = 0
        while True:
            try:
                check_count += 1
                print(f"\n--- Check #{check_count} at {datetime.now().strftime('%H:%M:%S')} ---")
                self.monitor_and_copy()
                print(f"💤 Waiting {interval_seconds} seconds until next check...")
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                print("🛑 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(10)  # Shorter retry delay

    def load_my_positions(self):
        """Stub method for loading positions"""
        return []

# Create a global bot instance
bot = SimpleCopyTrader()

# For manual testing
if __name__ == "__main__":
    # Run once
    bot.monitor_and_copy()