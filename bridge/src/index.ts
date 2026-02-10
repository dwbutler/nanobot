#!/usr/bin/env node
/**
 * nanobot WhatsApp Bridge
 * 
 * This bridge connects WhatsApp Web to nanobot's Python backend
 * via WebSocket. It handles authentication, message forwarding,
 * and reconnection logic.
 * 
 * Usage:
 *   npm run build && npm start
 *   
 * Or with custom settings:
 *   BRIDGE_PORT=3001 BRIDGE_HOST=127.0.0.1 BRIDGE_TOKEN=secret AUTH_DIR=~/.nanobot/whatsapp npm start
 */

// Polyfill crypto for Baileys in ESM
import { webcrypto } from 'crypto';
if (!globalThis.crypto) {
  (globalThis as any).crypto = webcrypto;
}

import { BridgeServer } from './server.js';
import { homedir } from 'os';
import { join } from 'path';

const PORT = parseInt(process.env.BRIDGE_PORT || '3001', 10);
const HOST = process.env.BRIDGE_HOST || '127.0.0.1';
const BRIDGE_TOKEN = process.env.BRIDGE_TOKEN || '';
const AUTH_DIR = process.env.AUTH_DIR || join(homedir(), '.nanobot', 'whatsapp-auth');

console.log('🐈 nanobot WhatsApp Bridge');
console.log('========================\n');

if (!BRIDGE_TOKEN && HOST !== '127.0.0.1' && HOST !== 'localhost') {
  console.error('BRIDGE_TOKEN is required when BRIDGE_HOST is not loopback');
  process.exit(1);
}

const server = new BridgeServer(PORT, HOST, AUTH_DIR, BRIDGE_TOKEN);

// Handle graceful shutdown
process.on('SIGINT', async () => {
  console.log('\n\nShutting down...');
  await server.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await server.stop();
  process.exit(0);
});

// Start the server
server.start().catch((error) => {
  console.error('Failed to start bridge:', error);
  process.exit(1);
});
