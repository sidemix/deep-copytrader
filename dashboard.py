from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
from datetime import datetime
from bot import bot

app = Flask(__name__)

@app.route('/')
def index():
    """Main dashboard"""
    bot.load_config()
    
    # Calculate wallet statistics
    wallet_stats = []
    for address, data in bot.config['copied_wallets'].items():
        if isinstance(data, dict):
            stats = {
                'address': address,
                'nickname': data.get('nickname', 'Unknown'),
                'active': data.get('active', True),
                'total_trades': data.get('total_trades', 0),
                'profitable_trades': data.get('profitable_trades', 0),
                'total_pnl': data.get('total_pnl', 0),
                'success_rate': (data.get('profitable_trades', 0) / data.get('total_trades', 1) * 100) if data.get('total_trades', 0) > 0 else 0
            }
            wallet_stats.append(stats)
    
    return render_template('index.html', 
                         config=bot.config,
                         wallet_stats=wallet_stats)

@app.route('/add_wallet', methods=['POST'])
def add_wallet():
    """Add a new wallet to copy"""
    address = request.form.get('address')
    nickname = request.form.get('nickname')
    
    if address and nickname:
        bot.config['copied_wallets'][address] = {
            'nickname': nickname,
            'active': True,
            'added_date': datetime.now().isoformat()
        }
        bot.save_config()
    
    return redirect(url_for('index'))

@app.route('/toggle_wallet/<address>')
def toggle_wallet(address):
    """Toggle wallet copying on/off"""
    if address in bot.config['copied_wallets']:
        wallet_data = bot.config['copied_wallets'][address]
        if isinstance(wallet_data, dict):
            wallet_data['active'] = not wallet_data.get('active', True)
            bot.save_config()
    
    return redirect(url_for('index'))

@app.route('/remove_wallet/<address>')
def remove_wallet(address):
    """Remove a wallet from copying"""
    if address in bot.config['copied_wallets']:
        del bot.config['copied_wallets'][address]
        bot.save_config()
    
    return redirect(url_for('index'))

@app.route('/toggle_bot')
def toggle_bot():
    """Start/stop the bot"""
    bot.config['bot_active'] = not bot.config['bot_active']
    bot.save_config()
    return redirect(url_for('index'))

@app.route('/toggle_test_mode')
def toggle_test_mode():
    """Toggle test mode"""
    bot.config['test_mode'] = not bot.config['test_mode']
    bot.save_config()
    return redirect(url_for('index'))

@app.route('/update_risk', methods=['POST'])
def update_risk():
    """Update risk percentage"""
    risk = request.form.get('risk_percentage')
    if risk and risk.isdigit():
        bot.config['risk_percentage'] = int(risk)
        bot.save_config()
    
    return redirect(url_for('index'))

@app.route('/run_bot')
def run_bot():
    """Manually trigger the bot to check for trades"""
    try:
        bot.monitor_and_copy()
        return "✅ Bot executed successfully - check Render logs for API calls"
    except Exception as e:
        return f"❌ Bot error: {str(e)}"

@app.route('/api/positions')
def get_positions():
    """API endpoint to get current positions"""
    positions = bot.load_my_positions()
    return jsonify(positions)

@app.route('/api/wallet_trades/<address>')
def get_wallet_trades(address):
    """API endpoint to get wallet trades"""
    trades = bot.get_wallet_trades(address)
    return jsonify(trades)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)