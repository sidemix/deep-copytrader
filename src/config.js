export const config = {
    polymarket: {
        baseURL: 'https://clob.polymarket.com',
        wsURL: 'wss://clob.polymarket.com/ws'
    },
    bot: {
        pollInterval: 10000, // 10 seconds
        testMode: true
    },
    // Common Polymarket token IDs (you'll need to expand this)
    tokenToMarketMap: {
        '0x...token1': 'US Election 2024 - Winner',
        '0x...token2': 'BTC Price 2025',
        // Add more token IDs as you encounter them
    }
};