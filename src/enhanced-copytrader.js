import { PolymarketAPI } from './polymarket-api.js';
import { config } from './config.js';

export class EnhancedCopyTrader {
    constructor() {
        this.polymarketAPI = new PolymarketAPI();
        this.copiedWallets = new Map();
        this.tradeHistory = [];
        this.isMonitoring = false;
        this.testMode = config.bot.testMode;
        
        // Statistics
        this.stats = {
            totalTrades: 0,
            profitableTrades: 0,
            totalPnl: 0,
            activeTrades: 0
        };
    }

    // Add wallet to copy
    async addWallet(walletAddress, nickname) {
        const walletData = {
            nickname,
            address: walletAddress.toLowerCase(),
            active: true,
            lastChecked: Date.now(),
            trades: []
        };

        this.copiedWallets.set(walletAddress.toLowerCase(), walletData);
        console.log(`✅ Added wallet: ${nickname} (${walletAddress})`);

        // Get existing orders immediately
        await this.pollWalletOrders(walletAddress);
        
        // Start monitoring if not already running
        if (!this.isMonitoring) {
            this.startMonitoring();
        }

        return walletData;
    }

    // Start monitoring all wallets
    startMonitoring() {
        this.isMonitoring = true;
        
        // Start polling
        this.startPolling();
        
        // Start WebSocket
        this.startWebSocket();
        
        console.log('🚀 Started monitoring Polymarket wallets');
    }

    // Poll wallets periodically
    startPolling() {
        setInterval(async () => {
            for (const [address, wallet] of this.copiedWallets) {
                if (wallet.active) {
                    await this.pollWalletOrders(address);
                }
            }
        }, config.bot.pollInterval);
    }

    // Start WebSocket for real-time updates
    startWebSocket() {
        this.polymarketAPI.connectWebSocket((data) => {
            this.handleWebSocketMessage(data);
        });

        // Subscribe to all wallets once connected
        setTimeout(() => {
            for (const [address, wallet] of this.copiedWallets) {
                if (wallet.active) {
                    this.polymarketAPI.subscribeToWallet(address);
                }
            }
        }, 2000);
    }

    // Poll specific wallet for orders
    async pollWalletOrders(walletAddress) {
        const orders = await this.polymarketAPI.getWalletOrders(walletAddress);
        
        orders.forEach(order => {
            this.processOrder(order);
        });

        return orders;
    }

    // Process incoming order
    processOrder(order) {
        const wallet = this.copiedWallets.get(order.trader.toLowerCase());
        if (!wallet) return;

        // Check if we've already seen this order
        const existingTrade = wallet.trades.find(t => t.id === order.id);
        
        if (!existingTrade) {
            // New order detected
            console.log(`🆕 New order detected: ${order.side} ${order.size} @ ${order.price} on ${order.market}`);
            
            const trade = this.createTradeRecord(order);
            wallet.trades.push(trade);
            this.tradeHistory.push(trade);
            
            this.stats.totalTrades++;
            
            if (order.status === 'OPEN') {
                this.stats.activeTrades++;
            }

            // Display in dashboard
            this.displayTrade(trade);

            // In test mode, we just display - no actual copying
            if (this.testMode) {
                console.log(`🧪 TEST MODE: Would copy trade from ${wallet.nickname}`);
            } else {
                // TODO: Implement actual copy trading logic
                this.executeCopyTrade(trade);
            }
        } else {
            // Update existing order
            this.updateTrade(existingTrade, order);
        }
    }

    // Create trade record
    createTradeRecord(order) {
        return {
            id: order.id,
            wallet: order.trader,
            nickname: this.copiedWallets.get(order.trader.toLowerCase())?.nickname || 'Unknown',
            market: order.market,
            side: order.side,
            size: order.size,
            price: order.price,
            status: order.status,
            token: order.token,
            createdAt: order.createdAt,
            detectedAt: new Date(),
            testMode: this.testMode,
            pnl: 0,
            outcome: 'PENDING'
        };
    }

    // Handle WebSocket messages
    handleWebSocketMessage(data) {
        if (data.type === 'order_created' || data.type === 'order_updated') {
            this.processOrder(this.polymarketAPI.parseOrders([data])[0]);
        } else if (data.type === 'order_filled') {
            console.log(`✅ Order filled: ${data.id}`);
            this.updateOrderStatus(data.id, 'FILLED');
        } else if (data.type === 'order_cancelled') {
            console.log(`❌ Order cancelled: ${data.id}`);
            this.updateOrderStatus(data.id, 'CANCELLED');
        }
    }

    // Update order status
    updateOrderStatus(orderId, status) {
        for (const [_, wallet] of this.copiedWallets) {
            const trade = wallet.trades.find(t => t.id === orderId);
            if (trade) {
                trade.status = status;
                trade.updatedAt = new Date();
                
                if (status === 'FILLED') {
                    this.stats.activeTrades--;
                    // TODO: Calculate actual P&L when position is closed
                }
                
                this.updateDashboard();
                break;
            }
        }
    }

    // Display trade in console (replace with your dashboard)
    displayTrade(trade) {
        const mode = trade.testMode ? '🧪 TEST' : '🚀 LIVE';
        console.log(`
${mode} TRADE DETECTED
────────────────────────
Wallet: ${trade.nickname} (${trade.wallet.substring(0, 8)}...)
Market: ${trade.market}
Action: ${trade.side} ${trade.size} shares
Price: $${trade.price}
Status: ${trade.status}
Time: ${trade.detectedAt.toLocaleTimeString()}
────────────────────────
        `);
    }

    // Get dashboard data
    getDashboardData() {
        const wallets = Array.from(this.copiedWallets.values()).map(wallet => ({
            nickname: wallet.nickname,
            address: wallet.address,
            active: wallet.active,
            trades: wallet.trades.length,
            profitable: wallet.trades.filter(t => t.pnl > 0).length,
            successRate: wallet.trades.length > 0 ? 
                (wallet.trades.filter(t => t.pnl > 0).length / wallet.trades.length * 100).toFixed(1) : 0,
            pnl: wallet.trades.reduce((sum, t) => sum + t.pnl, 0).toFixed(2)
        }));

        return {
            wallets,
            stats: this.stats,
            totalWallets: this.copiedWallets.size,
            testMode: this.testMode,
            lastUpdated: new Date()
        };
    }

    // Remove wallet
    removeWallet(walletAddress) {
        this.copiedWallets.delete(walletAddress.toLowerCase());
        console.log(`❌ Removed wallet: ${walletAddress}`);
    }

    // Pause/unpause wallet
    setWalletActive(walletAddress, active) {
        const wallet = this.copiedWallets.get(walletAddress.toLowerCase());
        if (wallet) {
            wallet.active = active;
            console.log(`${active ? '▶️' : '⏸️'} ${wallet.nickname} ${active ? 'activated' : 'paused'}`);
        }
    }
}

// For dashboard updates (you'll integrate this with your existing UI)
export function updateDashboard() {
    // This will be called from your frontend
    return copyTrader.getDashboardData();
}