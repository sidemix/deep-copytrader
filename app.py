from flask import Flask, render_template, request, jsonify
import requests
import sqlite3
from datetime import datetime
import os
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-123')

@app.route('/debug')
def debug():
    return "Flask is working! If you see this, the app is running correctly."

@app.route('/debug-template')
def debug_template():
    try:
        # Check if template folder exists
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        if not os.path.exists(template_path):
            return f"Template folder not found at: {template_path}"
        
        # Check if dashboard.html exists
        dashboard_path = os.path.join(template_path, 'dashboard.html')
        if not os.path.exists(dashboard_path):
            return f"dashboard.html not found at: {dashboard_path}"
        
        return f"Template folder found: {template_path}<br>dashboard.html found: {dashboard_path}"
    except Exception as e:
        return f"Error: {str(e)}"

# Database setup
def get_db_connection():
    conn = sqlite3.connect('trading_bot.db')
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
            # This would be replaced with actual Polymarket API calls
            # For now, return empty array - this is just for testing
            print(f"[DEBUG] Would fetch trades for: {wallet_address}")
            return []
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []
    
    def execute_trade(self, market_id, outcome, shares, price, trade_type):
        """Execute a trade on Polymarket"""
        if self.test_mode:
            print(f"[TEST] Would {trade_type} {shares} shares of {outcome} at ${price}")
            return {"status": "test_mode", "id": f"test_{int(time.time())}"}
        
        # Real trading would go here
        return {"status": "real_trade_disabled", "message": "Real trading not enabled"}

bot = PolymarketBot()

# Background trade copier (simple version)
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
                    print(f"[BOT] Checking wallet: {nickname}")
                    # This would actually copy trades in a real implementation
                    
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
    try:
        return render_template('dashboard.html')
    except Exception as e:
        return f"""
        <h1>Error Loading Dashboard</h1>
        <p>Error: {str(e)}</p>
        <p><a href="/debug">Test Debug Route</a></p>
        <p><a href="/debug-template">Test Template Debug</a></p>
        """

@app.route('/api/wallets', methods=['GET', 'POST'])
def manage_wallets():
    conn = get_db_connection()
    
    if request.method == 'POST':
        data = request.json
        address = data.get('address', '').strip()
        nickname = data.get('nickname', '').strip()
        
        if not address or not nickname:
            return jsonify({"status": "error", "message": "Address and nickname required"})
        
        c = conn.cursor()
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
    
    analytics = {
        'total_wallets': total_wallets,
        'total_trades': total_trades,
        'test_trades': test_trades,
        'live_trades': total_trades - test_trades,
        'bot_status': 'RUNNING' if bot.running else 'STOPPED',
        'mode': 'TEST DRY RUN' if bot.test_mode else 'LIVE',
        'risk_percentage': bot.risk_percentage
    }
    
    conn.close()
    return jsonify(analytics)

# Simple wallet stats endpoint
@app.route('/api/wallet-stats')
def get_wallet_stats():
    """Simple wallet performance stats"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        SELECT 
            w.id,
            w.nickname,
            w.address,
            w.active,
            COUNT(t.id) as total_trades,
            SUM(CASE WHEN t.status = 'test_mode' THEN 1 ELSE 0 END) as test_trades,
            SUM(CASE WHEN t.status = 'executed' THEN 1 ELSE 0 END) as live_trades
        FROM wallets w
        LEFT JOIN trades t ON w.id = t.wallet_id
        GROUP BY w.id, w.nickname, w.address
        ORDER BY w.created_at DESC
    ''')
    
    wallets = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return jsonify(wallets)

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)