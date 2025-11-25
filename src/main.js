import { EnhancedCopyTrader } from './enhanced-copytrader.js';

// Initialize the copy trader
const copyTrader = new EnhancedCopyTrader();

// Add your test wallet
await copyTrader.addWallet(
    '0x4a78fd566efcfd31a3143a392ce019459a24b918', 
    'LEEsomoney'
);

// You can add more wallets
// await copyTrader.addWallet('0x...', 'AnotherWallet');

console.log('Polymarket Copy Trader started!');
console.log('Monitoring wallets:', Array.from(copyTrader.copiedWallets.keys()));

// Export for use in your dashboard
export { copyTrader };