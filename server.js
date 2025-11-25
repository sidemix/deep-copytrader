import express from 'express';
import cors from 'cors';
import fetch from 'node-fetch';
import WebSocket from 'ws';

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Configuration
const config = {
    polymarket: {
        baseURL: 'https://clob.polymarket.com',
        wsURL: 'wss://clob.polymarket.com/ws'
    },
    testMode: true
};

// In-memory storage
const copiedWallets = new Map();
const tradeHistory = [];
let stats = {
    totalTrades: 0,
    activeTrades: 0,
    profitableTrades: 0,
    totalPnl: 0
};

// Polymarket API Class
class PolymarketAPI {
    constructor() {
        this.baseURL = config.polymarket.baseURL;
    }

    async getWalletOrders(walletAddress) {
        try {
            console.log(`Fetching orders for: ${walletAddress}`);
            const response = await fetch(`${this.baseURL}/orders?trader=${walletAddress.toLowerCase()}`);
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const orders = await response.json();
            console.log(`Found ${orders.length} orders for ${walletAddress}`);
            return this.parseOrders(orders);
        } catch (error) {
            console.error('Error fetching orders:', error);
            return [];
        }
    }

    parseOrders(orders) {
        return orders.map(order => ({
            id: order.id,
            trader: order.trader,
            token: order.token,
            price: parseFloat(order.price),
            size: parseFloat(order.size),
            side: order.side,
            status: order.status,
            market: this.extractMarketFromToken(order.token),
            createdAt: new Date(order.createdAt),
            filledAmount: parseFloat(order.filled || 0)
        }));
    }

    extractMarketFromToken(tokenId) {
        return `Market: ${tokenId.substring(0, 8)}...`;
    }
}

const polymarketAPI = new PolymarketAPI();

// Copy Trader Logic
class CopyTrader {
    async addWallet(walletAddress, nickname) {
        const walletData = {
            nickname,
            address: walletAddress.toLowerCase(),
            active: true,
            lastChecked: Date.now(),
            trades: [],
            stats: {
                trades: 0,
                profitable: 0,
                successRate: 0,
                pnl: 0
            }
        };

        copiedWallets.set(walletAddress.toLowerCase(), walletData);
        console.log(`✅ Added wallet: ${nickname}`);

        // Get existing orders
        await this.pollWalletOrders(walletAddress);
        this.startPolling();

        return walletData;
    }

    startPolling() {
        // Poll every 30 seconds
        if (!this.pollInterval) {
            this.pollInterval = setInterval(async () => {
                for (const [address, wallet] of copiedWallets) {
                    if (wallet.active) {
                        await this.pollWalletOrders(address);
                    }
                }
            }, 30000);
        }
    }

    async pollWalletOrders(walletAddress) {
        const orders = await polymarketAPI.getWalletOrders(walletAddress);
        const wallet = copiedWallets.get(walletAddress.toLowerCase());
        
        if (!wallet) return;

        orders.forEach(order => {
            this.processOrder(order, wallet);
        });

        this.updateWalletStats(wallet);
    }

    processOrder(order, wallet) {
        const existingTrade = wallet.trades.find(t => t.id === order.id);
        
        if (!existingTrade) {
            console.log(`🆕 New order: ${order.side} ${order.size} @ $${order.price}`);
            
            const trade = {
                id: order.id,
                wallet: order.trader,
                nickname: wallet.nickname,
                market: order.market,
                side: order.side,
                size: order.size,
                price: order.price,
                status: order.status,
                createdAt: order.createdAt,
                detectedAt: new Date(),
                testMode: config.testMode
            };

            wallet.trades.push(trade);
            tradeHistory.push(trade);
            stats.totalTrades++;

            if (order.status === 'OPEN') {
                stats.activeTrades++;
            }
        }
    }

    updateWalletStats(wallet) {
        const trades = wallet.trades;
        wallet.stats.trades = trades.length;
        wallet.stats.profitable = trades.filter(t => t.pnl > 0).length;
        wallet.stats.successRate = trades.length > 0 ? 
            (wallet.stats.profitable / trades.length * 100).toFixed(1) : 0;
        wallet.stats.pnl = trades.reduce((sum, t) => sum + (t.pnl || 0), 0).toFixed(2);
    }

    removeWallet(walletAddress) {
        copiedWallets.delete(walletAddress.toLowerCase());
    }

    setWalletActive(walletAddress, active) {
        const wallet = copiedWallets.get(walletAddress.toLowerCase());
        if (wallet) {
            wallet.active = active;
        }
    }

    getDashboardData() {
        const wallets = Array.from(copiedWallets.values()).map(wallet => ({
            nickname: wallet.nickname,
            address: wallet.address,
            active: wallet.active,
            trades: wallet.stats.trades,
            profitable: wallet.stats.profitable,
            successRate: wallet.stats.successRate,
            pnl: wallet.stats.pnl
        }));

        return {
            wallets,
            stats,
            totalWallets: copiedWallets.size,
            testMode: config.testMode,
            lastUpdated: new Date()
        };
    }
}

const copyTrader = new CopyTrader();

// API Routes
app.get('/api/dashboard-data', (req, res) => {
    const data = copyTrader.getDashboardData();
    res.json(data);
});

app.post('/api/add-wallet', async (req, res) => {
    const { walletAddress, nickname } = req.body;
    
    try {
        const wallet = await copyTrader.addWallet(walletAddress, nickname);
        res.json({ success: true, wallet });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/api/remove-wallet', (req, res) => {
    const { walletAddress } = req.body;
    copyTrader.removeWallet(walletAddress);
    res.json({ success: true });
});

app.post('/api/set-wallet-active', (req, res) => {
    const { walletAddress, active } = req.body;
    copyTrader.setWalletActive(walletAddress, active);
    res.json({ success: true });
});

// Serve HTML Dashboard
app.get('/', (req, res) => {
    res.sendFile(process.cwd() + '/public/index.html');
});

// Initialize with your wallet
async function initialize() {
    await copyTrader.addWallet(
        '0x4a78fd566efcfd31a3143a392ce019459a24b918', 
        'LEEsomoney'
    );
    console.log('🚀 Polymarket Copy Trader Started on Render');
}

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    initialize();
});