import json
import time
import requests
import schedule
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class PolymarketCopyTrader:
    def __init__(self):
        self.load_config()
        self.session = requests.Session()
        self.setup_auth()
        
    def load_config(self):
        with open('config.json', 'r') as f:
            self.config = json.load(f)
    
    def save_config(self):
        with open('config.json', 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def setup_auth(self):
        # Get API credentials from environment variables
        api_key = os.getenv('POLYMARKET_API_KEY')
        api_secret = os.getenv('POLYMARKET_API_SECRET')
        passphrase = os.getenv('POLYMARKET_PASSPHRASE')
        
        if not all([api_key, api_secret, passphrase]):
            print("Warning: API credentials not found in environment variables")
            if not self.config['test_mode']:
                print("Cannot run in live mode without API credentials")
        
        # Set up authentication headers
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
        
        # For requests that need signature (you may need to implement signing)
        self.api_secret = api_secret
        self.passphrase = passphrase
    
    def sign_request(self, method, path, body=None):
        """Implement request signing if required by Polymarket API"""
        # This is a placeholder - implement based on Polymarket's specific auth requirements
        timestamp = str(int(time.time()))
        message = timestamp + method + path + (body or '')
        # Implement actual signing logic here based on Polymarket's documentation
        return timestamp
    
    def get_wallet_trades(self, wallet_address):
        """Get recent trades for a specific wallet"""
        try:
            url = f"{self.config['base_url']}/trades"
            params = {'account': wallet_address, 'limit': 50}
            
            # Add signature if needed
            if not self.config['test_mode']:
                signature = self.sign_request('GET', '/trades')
                self.session.headers.update({'X-Signature': signature})
            
            response = self.session.get(url, params=params)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Error getting trades for {wallet_address}: {e}")
            return []
    
    def get_current_positions(self, wallet_address):
        """Get current positions for a wallet"""
        try:
            url = f"{self.config['base_url']}/positions"
            params = {'account': wallet_address}
            
            # Add signature if needed
            if not self.config['test_mode']:
                signature = self.sign_request('GET', '/positions')
                self.session.headers.update({'X-Signature': signature})
            
            response = self.session.get(url, params=params)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Error getting positions for {wallet_address}: {e}")
            return []
    
    def place_order(self, condition_id, outcome, amount, price):
        """Place an order on Polymarket"""
        if self.config['test_mode']:
            print(f"TEST MODE: Would place order - {condition_id}, {outcome}, ${amount} @ {price}")
            return {'id': 'test_order_' + str(int(time.time()))}
        
        try:
            url = f"{self.config['base_url']}/orders"
            order_data = {
                'condition_id': condition_id,
                'outcome': outcome,
                'amount': str(amount),
                'price': str(price),
                'side': 'buy'
            }
            
            # Add signature if needed
            signature = self.sign_request('POST', '/orders', json.dumps(order_data))
            self.session.headers.update({'X-Signature': signature})
            
            response = self.session.post(url, json=order_data)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Error placing order: {e}")
            return None
    
    def close_position(self, position_id):
        """Close a position"""
        if self.config['test_mode']:
            print(f"TEST MODE: Would close position {position_id}")
            return True
        
        try:
            url = f"{self.config['base_url']}/positions/{position_id}/close"
            
            # Add signature if needed
            signature = self.sign_request('POST', f'/positions/{position_id}/close')
            self.session.headers.update({'X-Signature': signature})
            
            response = self.session.post(url)
            return response.status_code == 200
        except Exception as e:
            print(f"Error closing position: {e}")
            return False
    
    def calculate_trade_amount(self, wallet_size_percentage):
        """Calculate trade amount based on risk percentage"""
        base_amount = 10  # $10 base - you might want to get this from account balance
        risk_pct = self.config['risk_percentage'] / 100
        return base_amount * risk_pct * (wallet_size_percentage / 100)
    
    def sync_wallet_trades(self, wallet_address, nickname):
        """Sync trades for a specific wallet"""
        if not self.config['bot_active']:
            return
        
        print(f"Syncing trades for {nickname} ({wallet_address})")
        
        current_positions = self.get_current_positions(wallet_address)
        my_positions = self.load_my_positions()
        
        # Track wallet's current positions
        wallet_active_trades = {}
        for position in current_positions:
            key = f"{position['condition_id']}_{position['outcome']}"
            wallet_active_trades[key] = position
        
        # Close positions that wallet has closed
        for my_pos_key, my_pos in list(my_positions.items()):
            if my_pos['copied_from'] == wallet_address and my_pos_key not in wallet_active_trades:
                print(f"Closing position {my_pos['position_id']} - wallet exited")
                if self.close_position(my_pos['position_id']):
                    del my_positions[my_pos_key]
                    self.record_trade_result(my_pos, 'closed')
        
        # Open new positions that wallet has
        for pos_key, position in wallet_active_trades.items():
            if pos_key not in my_positions:
                print(f"Copying new position from {nickname}: {position['condition_id']}")
                
                trade_amount = self.calculate_trade_amount(100)
                order_result = self.place_order(
                    position['condition_id'],
                    position['outcome'],
                    trade_amount,
                    position['current_price']
                )
                
                if order_result:
                    my_positions[pos_key] = {
                        'position_id': order_result.get('id'),
                        'condition_id': position['condition_id'],
                        'outcome': position['outcome'],
                        'amount': trade_amount,
                        'entry_price': position['current_price'],
                        'copied_from': wallet_address,
                        'copied_from_nickname': nickname,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'open'
                    }
        
        self.save_my_positions(my_positions)
        self.update_wallet_stats(wallet_address, nickname)
    
    def load_my_positions(self):
        """Load my current positions from file"""
        try:
            with open('trades.json', 'r') as f:
                data = json.load(f)
                return data.get('positions', {})
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
    
    def save_my_positions(self, positions):
        """Save my positions to file"""
        try:
            with open('trades.json', 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        data['positions'] = positions
        data['last_updated'] = datetime.now().isoformat()
        
        with open('trades.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_trade_result(self, position, result):
        """Record trade results for analytics"""
        # Implement trade result tracking
        pass
    
    def update_wallet_stats(self, wallet_address, nickname):
        """Update performance statistics for a wallet"""
        if wallet_address not in self.config['copied_wallets']:
            self.config['copied_wallets'][wallet_address] = {}
        
        stats = self.config['copied_wallets'][wallet_address]
        
        if 'nickname' not in stats:
            stats['nickname'] = nickname
            stats['total_trades'] = 0
            stats['profitable_trades'] = 0
            stats['total_pnl'] = 0
            stats['last_updated'] = datetime.now().isoformat()
            stats['active'] = True
        
        self.save_config()
    
    def check_and_copy_trades(self):
        """Main function to check and copy all wallet trades"""
        print(f"Checking trades at {datetime.now()}")
        
        if not self.config['bot_active']:
            print("Bot is not active - skipping check")
            return
        
        for wallet_address, wallet_data in self.config['copied_wallets'].items():
            if isinstance(wallet_data, dict) and wallet_data.get('active', True):
                self.sync_wallet_trades(wallet_address, wallet_data.get('nickname', 'Unknown'))
    
    def run_scheduler(self):
        """Run the bot on a schedule"""
        schedule.every(1).minutes.do(self.check_and_copy_trades)
        
        print("Bot scheduler started. Checking every minute...")
        while True:
            schedule.run_pending()
            time.sleep(1)

# Global bot instance
bot = PolymarketCopyTrader()

if __name__ == "__main__":
    print("Starting Polymarket Copy Trader...")
    print(f"Test Mode: {bot.config['test_mode']}")
    print(f"Bot Active: {bot.config['bot_active']}")
    bot.run_scheduler()