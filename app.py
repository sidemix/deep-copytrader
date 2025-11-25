import os
from flask import Flask, render_template, request, jsonify
import requests
import json
import time
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database setup
def get_db_connection():
    # Use Railway's persistent volume if available, otherwise local
    db_path = os.environ.get('DATABASE_URL', 'trading_bot.db')
    if db_path.startswith('postgres://'):
        # For PostgreSQL on Railway, you'd need to adapt this
        # For now, we'll stick with SQLite for simplicity
        db_path = 'trading_bot.db'
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Wallets table
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (id INTEGER PRIMARY KEY, address TEXT, nickname TEXT, 
                  active INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Trades table
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY, wallet_id INTEGER, market_id TEXT,
                  outcome TEXT, shares REAL, price REAL, type TEXT,
                  timestamp TIMESTAMP, status TEXT)''')
    
    # Bot settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Initialize default settings
    c.execute('''INSERT OR IGNORE INTO settings (key, value) VALUES 
                 ('risk_percentage', '10'),
                 ('test_mode', 'true')''')
    
    conn.commit()
    conn.close()

init_db()

class PolymarketBot:
    def __init__(self):
        self.running = False
        self.test_mode = True
        self.risk_percentage = 10
        
    def get_wallet_trades(self, wallet_address):
        """Get recent trades for a wallet address"""
        try:
            # Polymarket API endpoint - you'll need to update this with actual endpoints
            url = f"https://gamma-api.polymarket.com/account/{wallet_address}/trades"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            print(f"API returned status {response.status_code}")
            return []
        except Exception as e:
            print(f"Error fetching trades for {wallet_address}: {e}")
            return []
    
    def execute_trade(self, market_id, outcome, shares, price, trade_type):
        """Execute a trade on Polymarket"""
        if self.test_mode:
            print(f"TEST MODE - Would execute: {trade_type} {shares} shares of {outcome} at ${price}")
            return {"status": "test_mode", "id": f"test_{int(time.time())}"}
        
        # Real trading implementation
        try:
            # You'll need to implement actual Polymarket API integration here
            # This requires API keys and proper authentication
            api_key = os.environ.get('POLYMARKET_API_KEY')
            if not api_key:
                return {"status": "error", "message": "API key not configured"}
            
            # Placeholder for real API call
            # headers = {'Authorization': f'Bearer {api_key}'}
            # data = {
            #     'market': market_id, 
            #     'outcome': outcome, 
            #     'shares': shares, 
            #     'price': price, 
            #     'type': trade_type
            # }
            # response = requests.post('https://api.polymarket.com/trade', 
            #                        headers=headers, json=data, timeout=30)
            # return response.json()
            
            return {"status": "real_trade_disabled", "message": "Real trading not yet implemented"}
            
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def copy_trade(self, wallet_address, nickname):
        """Copy trades from a specific wallet"""
        if not self.running:
            return []
            
        trades = self.get_wallet_trades(wallet_address)
        copied_trades = []
        
        for trade in trades[-5:]:  # Get last 5 trades to avoid rate limiting
            # Parse trade data - adjust based on actual API response
            market_id = trade.get('market_id', trade.get('market', ''))
            outcome = trade.get('outcome', 'YES')  # Default to YES outcome
            shares = float(trade.get('shares', 0))
            price = float(trade.get('price', 0))
            trade_type = trade.get('type', 'buy').lower()
            
            if shares <= 0 or price <= 0:
                continue
                
            # Apply risk management
            risk_adjusted_shares = shares * (self.risk_percentage / 100)
            
            # Execute the copied trade
            result = self.execute_trade(market_id, outcome, risk_adjusted_shares, price, trade_type)
            
            # Store trade in database
            conn = get_db_connection()
            c = conn.cursor()
            wallet_id = self.get_wallet_id(conn, wallet_address)
            
            c.execute('''INSERT INTO trades 
                        (wallet_id, market_id, outcome, shares, price, type, status, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                     (wallet_id, market_id, outcome, risk_adjusted_shares, price, 
                      trade_type, result.get('status', 'unknown'), datetime.now()))
            conn.commit()
            conn.close()
            
            copied_trades.append({
                'market_id': market_id,
                'outcome': outcome,
                'shares': risk_adjusted_shares,
                'price': price,
                'type': trade_type,
                'result': result,
                'timestamp': datetime.now()
            })
            
            # Small delay to avoid rate limiting
            time.sleep(1)
            
        return copied_trades
    
    def get_wallet_id(self, conn, address):
        """Get wallet ID from address"""
        c = conn.cursor()
        c.execute("SELECT id FROM wallets WHERE address = ?", (address,))
        result = c.fetchone()
        return result[0] if result else None

bot = PolymarketBot()

# Background trade copier thread
def trade_copier():
    while True:
        if bot.running:
            try:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT address, nickname FROM wallets WHERE active = 1")
                wallets = c.fetchall()
                conn.close()
                
                for wallet in wallets:
                    address, nickname = wallet
                    print(f"Copying trades for {nickname} ({address})")
                    bot.copy_trade(address, nickname)
                    
            except Exception as e:
                print(f"Error in trade copier: {e}")
        
        time.sleep(60)  # Check every minute

# Start background thread
import threading
copier_thread = threading.Thread(target=trade_copier, daemon=True)
copier_thread.start()

# Routes
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/wallets', methods=['GET', 'POST'])
def manage_wallets():
    conn = get_db_connection()
    
    if request.method == 'POST':
        data = request.json
        address = data.get('address', '').strip()
        nickname = data.get('nickname', '').strip()
        
        if not address or not nickname:
            return jsonify({"status": "error", "message": "Address and nickname required"})
        
        # Check if wallet already exists
        c = conn.cursor()
        c.execute("SELECT id FROM wallets WHERE address = ?", (address,))
        if c.fetchone():
            return jsonify({"status": "error", "message": "Wallet already exists"})
        
        c.execute("INSERT INTO wallets (address, nickname, active) VALUES (?, ?, 1)", 
                 (address, nickname))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": "Wallet added"})
    
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM wallets ORDER BY created_at DESC")
        wallets = [dict(row) for row in c.fetchall()]
        conn.close()
        return jsonify(wallets)

@app.route('/api/wallets/<int:wallet_id>', methods=['DELETE'])
def delete_wallet(wallet_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Wallet deleted"})

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    data = request.json
    bot.test_mode = data.get('test_mode', True)
    bot.running = True
    
    # Update settings
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
             ('test_mode', str(bot.test_mode).lower()))
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "success", 
        "message": f"Bot started in {'TEST' if bot.test_mode else 'LIVE'} mode"
    })

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    bot.running = False
    return jsonify({"status": "success", "message": "Bot stopped"})

@app.route('/api/bot/status')
def bot_status():
    return jsonify({
        "running": bot.running,
        "test_mode": bot.test_mode,
        "risk_percentage": bot.risk_percentage
    })

@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        risk_percentage = data.get('risk_percentage')
        
        if risk_percentage and 1 <= risk_percentage <= 100:
            bot.risk_percentage = risk_percentage
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                     ('risk_percentage', str(risk_percentage)))
            conn.commit()
        
        conn.close()
        return jsonify({"status": "success", "message": "Settings updated"})
    
    else:
        c.execute("SELECT * FROM settings")
        settings = {row[0]: row[1] for row in c.fetchall()}
        conn.close()
        return jsonify(settings)

@app.route('/api/analytics')
def get_analytics():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM wallets")
    total_wallets = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM trades")
    total_trades = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM trades WHERE status = 'test_mode'")
    test_trades = c.fetchone()[0]
    
    # Get wallet performance (simplified)
    c.execute('''SELECT w.nickname, COUNT(t.id) as trade_count 
                 FROM wallets w LEFT JOIN trades t ON w.id = t.wallet_id 
                 GROUP BY w.id, w.nickname''')
    wallet_stats = [dict(row) for row in c.fetchall()]
    
    analytics = {
        'total_wallets': total_wallets,
        'total_trades': total_trades,
        'test_trades': test_trades,
        'live_trades': total_trades - test_trades,
        'bot_status': 'RUNNING' if bot.running else 'STOPPED',
        'mode': 'TEST DRY RUN' if bot.test_mode else 'LIVE',
        'risk_percentage': bot.risk_percentage,
        'wallet_stats': wallet_stats
    }
    
    conn.close()
    return jsonify(analytics)

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)