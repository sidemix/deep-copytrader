from flask import Flask, render_template, request, jsonify, redirect, url_for
import json
from datetime import datetime
from bot import bot
import os

app = Flask(__name__)

def get_wallets_from_env():
    """Get wallets from environment variable as backup"""
    wallets_json = os.getenv('WALLETS', '{}')
    try:
        return json.loads(wallets_json)
    except:
        return {}

def save_wallets_to_env(wallets):
    """Tell user how to update environment variable"""
    wallets_json = json.dumps(wallets)
    print(f"🔧 MANUAL STEP: Update WALLETS environment variable to:")
    print(wallets_json)
    return wallets_json

def update_environment_wallets(wallets):
    """Print instructions to update environment variables"""
    print("🔧 UPDATE REQUIRED: Copy this to your Render environment variables:")
    print(f"WALLETS={json.dumps(wallets)}")
    return True

@app.route('/')
def index():
    """Main dashboard"""
    try:
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
    except Exception as e:
        return f"Error loading dashboard: {str(e)}", 500

@app.route('/add_wallet', methods=['POST'])
def add_wallet():
    address = request.form.get('address')
    nickname = request.form.get('nickname')
    
    if address and nickname:
        bot.config['copied_wallets'][address] = {
            'nickname': nickname,
            'active': True,
            'added_date': datetime.now().isoformat()
        }
        bot.save_config()  # This will print instructions
        
        # Also print to logs
        print(f"➕ Added wallet: {nickname} ({address})")
        print(f"📋 Total wallets: {len(bot.config['copied_wallets'])}")
    
    return redirect(url_for('index'))

@app.route('/debug_disk_detailed')
def debug_disk_detailed():
    """Detailed disk debugging"""
    import os
    import stat
    
    results = []
    results.append("=== DETAILED DISK DEBUG ===")
    
    # Check various paths
    paths = [
        '/',
        '/opt', 
        '/opt/data',
        '/opt/data/config.json',
        'config.json'
    ]
    
    for path in paths:
        exists = os.path.exists(path)
        results.append(f"{path}: {'EXISTS' if exists else 'MISSING'}")
        
        if exists:
            try:
                # Check if it's a directory or file
                if os.path.isdir(path):
                    results.append(f"  Type: Directory")
                    # List contents if it's /opt/data
                    if path == '/opt/data':
                        try:
                            contents = os.listdir(path)
                            results.append(f"  Contents: {contents}")
                        except:
                            results.append(f"  Cannot list contents")
                else:
                    results.append(f"  Type: File")
                    results.append(f"  Size: {os.path.getsize(path)} bytes")
                
                # Check permissions
                st = os.stat(path)
                results.append(f"  Permissions: {oct(st.st_mode)}")
                results.append(f"  Owner: {st.st_uid}:{st.st_gid}")
                
            except Exception as e:
                results.append(f"  Error: {e}")
    
    # Test writing to disk
    results.append("=== WRITE TEST ===")
    test_path = '/opt/data/test_write.txt'
    try:
        with open(test_path, 'w') as f:
            f.write('test content')
        results.append(f"✅ SUCCESS: Can write to {test_path}")
        os.remove(test_path)
    except Exception as e:
        results.append(f"❌ FAILED: Cannot write to {test_path}: {e}")
    
    return "<br>".join(results)

@app.route('/toggle_wallet/<address>')
def toggle_wallet(address):
    """Toggle wallet copying on/off"""
    if address in bot.config['copied_wallets']:
        wallet_data = bot.config['copied_wallets'][address]
        if isinstance(wallet_data, dict):
            wallet_data['active'] = not wallet_data.get('active', True)
            bot.save_config()
            
            # Update environment variable backup
            env_wallets = get_wallets_from_env()
            if address in env_wallets:
                env_wallets[address]['active'] = wallet_data['active']
                save_wallets_to_env(env_wallets)
    
    return redirect(url_for('index'))

@app.route('/health')
def health():
    """Simple health check"""
    return "OK - App is running"

@app.route('/debug_storage')
def debug_storage():
    """Debug route to check storage locations"""
    import os
    results = []
    
    paths_to_check = ['/opt/data/config.json', 'config.json']
    
    for path in paths_to_check:
        exists = os.path.exists(path)
        results.append(f"{path}: {'EXISTS' if exists else 'MISSING'}")
        
        if exists:
            try:
                with open(path, 'r') as f:
                    content = json.load(f)
                    results.append(f"  Content: {len(content.get('copied_wallets', {}))} wallets")
            except Exception as e:
                results.append(f"  Error reading: {e}")
    
    return "<br>".join(results)

@app.route('/remove_wallet/<address>')
def remove_wallet(address):
    """Remove a wallet from copying"""
    if address in bot.config['copied_wallets']:
        del bot.config['copied_wallets'][address]
        bot.save_config()
        
        # Update environment variable backup
        env_wallets = get_wallets_from_env()
        if address in env_wallets:
            del env_wallets[address]
            save_wallets_to_env(env_wallets)
    
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

@app.route('/debug_simple')
def debug_simple():
    """Simple disk debug without complex operations"""
    import os
    
    results = []
    results.append("=== Simple Disk Debug ===")
    
    # Check basic paths
    paths = ['/', '/opt', '/opt/data', '/opt/data/config.json', 'config.json']
    
    for path in paths:
        exists = os.path.exists(path)
        results.append(f"{path}: {'EXISTS' if exists else 'MISSING'}")
    
    return "<br>".join(results)


@app.route('/run_bot')
def run_bot():
    """Manually trigger the bot to check for trades"""
    try:
        # Force reload config to get latest wallets
        bot.load_config()
        print("🚀 Starting bot monitoring...")
        bot.monitor_and_copy()
        print("✅ Bot monitoring completed")
        return "✅ Bot executed successfully - check Render logs for API calls"
    except Exception as e:
        print(f"❌ Bot error: {e}")
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