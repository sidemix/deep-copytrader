import os
import time
import hmac
import hashlib
import base64
import json
from flask import Flask, render_template, request, jsonify
import requests
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

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
                  active INTEGER, total_profit REAL DEFAULT 0,
                  total_trades INTEGER DEFAULT 0, winning_trades INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Trades table with profit tracking
    c.execute('''CREATE TABLE IF NOT EXISTS trades
                 (id INTEGER PRIMARY KEY, wallet_id INTEGER, market_id TEXT,
                  outcome TEXT, shares REAL, price REAL, type TEXT,
                  profit_loss REAL DEFAULT 0, status TEXT,
                  timestamp TIMESTAMP, closed_at TIMESTAMP)''')
    
    # Bot settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

class PolymarketBot:
    def __init__(self):
        self.running = False
        self.test_mode = True
        self.risk_percentage = 10
        self.api_key = os.environ.get('POLYMARKET_API_KEY')
        self.api_secret = os.environ.get('POLYMARKET_API_SECRET')
        self.passphrase = os.environ.get('POLYMARKET_PASSPHRASE')
        self.funding_wallet = os.environ.get('FUNDING_WALLET_ADDRESS')
    
    def get_wallet_performance(self, wallet_id):
        """Get detailed performance metrics for a specific wallet"""
        conn = get_db_connection()
        c = conn.cursor()
        
        # Get wallet basic info
        c.execute('''SELECT * FROM wallets WHERE id = ?''', (wallet_id,))
        wallet = dict(c.fetchone()) if c.fetchone() else None
        
        if not wallet:
            conn.close()
            return None
        
        # Get trade statistics
        c.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit_loss) as total_profit,
                AVG(profit_loss) as avg_profit_per_trade,
                MAX(profit_loss) as best_trade,
                MIN(profit_loss) as worst_trade
            FROM trades 
            WHERE wallet_id = ? AND status = 'closed'
        ''', (wallet_id,))
        
        stats = dict(c.fetchone())
        
        # Get recent trades
        c.execute('''
            SELECT * FROM trades 
            WHERE wallet_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (wallet_id,))
        recent_trades = [dict(row) for row in c.fetchall()]
        
        # Calculate win rate
        win_rate = (stats['winning_trades'] / stats['total_trades'] * 100) if stats['total_trades'] > 0 else 0
        
        performance = {
            'wallet_info': wallet,
            'stats': {
                'total_trades': stats['total_trades'] or 0,
                'winning_trades': stats['winning_trades'] or 0,
                'losing_trades': stats['losing_trades'] or 0,
                'win_rate': round(win_rate, 2),
                'total_profit': stats['total_profit'] or 0,
                'avg_profit_per_trade': stats['avg_profit_per_trade'] or 0,
                'best_trade': stats['best_trade'] or 0,
                'worst_trade': stats['worst_trade'] or 0,
                'profitability': 'Profitable' if (stats['total_profit'] or 0) > 0 else 'Losing'
            },
            'recent_trades': recent_trades
        }
        
        conn.close()
        return performance
    
    def get_all_wallets_performance(self):
        """Get performance overview for all wallets"""
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            SELECT 
                w.id,
                w.nickname,
                w.address,
                w.active,
                COUNT(t.id) as total_trades,
                SUM(CASE WHEN t.profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(t.profit_loss) as total_profit,
                CASE 
                    WHEN COUNT(t.id) > 0 THEN 
                        ROUND((SUM(CASE WHEN t.profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(t.id)), 2)
                    ELSE 0 
                END as win_rate,
                w.created_at
            FROM wallets w
            LEFT JOIN trades t ON w.id = t.wallet_id AND t.status = 'closed'
            GROUP BY w.id, w.nickname, w.address
            ORDER BY total_profit DESC
        ''')
        
        wallets_performance = []
        for row in c.fetchall():
            wallet_data = dict(row)
            
            # Determine performance rating
            total_profit = wallet_data['total_profit'] or 0
            win_rate = wallet_data['win_rate'] or 0
            
            if total_profit > 0 and win_rate > 60:
                performance_rating = 'Excellent'
            elif total_profit > 0 and win_rate > 50:
                performance_rating = 'Good'
            elif total_profit > 0:
                performance_rating = 'Fair'
            elif total_profit == 0:
                performance_rating = 'Neutral'
            else:
                performance_rating = 'Poor'
            
            wallet_data['performance_rating'] = performance_rating
            wallet_data['status_badge'] = 'active' if wallet_data['active'] else 'inactive'
            
            wallets_performance.append(wallet_data)
        
        conn.close()
        return wallets_performance

    def archive_wallet(self, wallet_id):
        """Archive a wallet (set inactive)"""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE wallets SET active = 0 WHERE id = ?', (wallet_id,))
        conn.commit()
        conn.close()
        return True
    
    def activate_wallet(self, wallet_id):
        """Reactivate a wallet"""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('UPDATE wallets SET active = 1 WHERE id = ?', (wallet_id,))
        conn.commit()
        conn.close()
        return True

    # ... (keep your existing get_wallet_trades, execute_trade, copy_trade methods)

bot = PolymarketBot()

# Enhanced API Routes
@app.route('/api/wallets/performance')
def get_wallets_performance():
    """Get performance data for all wallets"""
    try:
        performance_data = bot.get_all_wallets_performance()
        return jsonify(performance_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wallets/<int:wallet_id>/performance')
def get_wallet_performance(wallet_id):
    """Get detailed performance for a specific wallet"""
    try:
        performance = bot.get_wallet_performance(wallet_id)
        if performance:
            return jsonify(performance)
        else:
            return jsonify({'error': 'Wallet not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wallets/<int:wallet_id>/archive', methods=['POST'])
def archive_wallet(wallet_id):
    """Archive a wallet"""
    try:
        success = bot.archive_wallet(wallet_id)
        if success:
            return jsonify({'status': 'success', 'message': 'Wallet archived'})
        else:
            return jsonify({'error': 'Wallet not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/wallets/<int:wallet_id>/activate', methods=['POST'])
def activate_wallet(wallet_id):
    """Activate a wallet"""
    try:
        success = bot.activate_wallet(wallet_id)
        if success:
            return jsonify({'status': 'success', 'message': 'Wallet activated'})
        else:
            return jsonify({'error': 'Wallet not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ... (keep your existing routes)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)