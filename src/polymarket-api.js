import fetch from 'node-fetch';
import WebSocket from 'ws';
import { config } from './config.js';

export class PolymarketAPI {
    constructor() {
        this.baseURL = config.polymarket.baseURL;
        this.wsURL = config.polymarket.wsURL;
        this.ws = null;
        this.subscribers = new Set();
    }

    // Get all orders for a specific wallet
    async getWalletOrders(walletAddress) {
        try {
            console.log(`Fetching orders for wallet: ${walletAddress}`);
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

    // Parse orders into standardized format
    parseOrders(orders) {
        return orders.map(order => ({
            id: order.id,
            trader: order.trader,
            token: order.token,
            price: parseFloat(order.price),
            size: parseFloat(order.size),
            side: order.side, // "BUY" or "SELL"
            status: order.status, // "OPEN", "FILLED", "CANCELLED"
            market: this.extractMarketFromToken(order.token),
            createdAt: new Date(order.createdAt),
            filledAmount: parseFloat(order.filled || 0),
            rawData: order // Keep original data for debugging
        }));
    }

    // Extract market info from token ID
    extractMarketFromToken(tokenId) {
        // For now, return token ID - you'll need to build a mapping
        return config.tokenToMarketMap[tokenId] || `Market: ${tokenId.substring(0, 8)}...`;
    }

    // WebSocket connection for real-time updates
    connectWebSocket(onMessage) {
        this.ws = new WebSocket(this.wsURL);
        
        this.ws.on('open', () => {
            console.log('✅ Connected to Polymarket WebSocket');
        });

        this.ws.on('message', (data) => {
            try {
                const parsed = JSON.parse(data);
                onMessage(parsed);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        });

        this.ws.on('error', (error) => {
            console.error('WebSocket error:', error);
        });

        this.ws.on('close', () => {
            console.log('WebSocket connection closed');
            // Attempt reconnect after delay
            setTimeout(() => this.connectWebSocket(onMessage), 5000);
        });

        return this.ws;
    }

    // Subscribe to order updates for a wallet
    subscribeToWallet(walletAddress) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'subscribe',
                channel: 'orders',
                trader: walletAddress.toLowerCase()
            }));
            console.log(`Subscribed to orders for: ${walletAddress}`);
        }
    }

    // Get market information for a token
    async getMarketInfo(tokenId) {
        try {
            const response = await fetch(`${this.baseURL}/markets?token_id=${tokenId}`);
            const markets = await response.json();
            return markets[0] || null;
        } catch (error) {
            console.error('Error fetching market info:', error);
            return null;
        }
    }
}