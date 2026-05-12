import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';
import cors from 'cors';
import morgan from 'morgan';
import computeRouter from './routes/compute.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const app = express();
const PORT = 3000;

// Rate limiting: Track requests by IP
const ipRequests = new Map();
const RATE_LIMIT_WINDOW = 60000; // 1 minute
const RATE_LIMIT_MAX = 60; // Max 60 requests per minute
const BLOCK_DURATION = 10000; // Block for 10 seconds if exceeded

const rateLimiter = (req, res, next) => {
  const ip = req.ip || req.headers['x-forwarded-for'] || req.connection.remoteAddress || 'unknown';
  const now = Date.now();

  if (!ipRequests.has(ip)) {
    ipRequests.set(ip, { requests: [], blockedUntil: 0 });
  }

  const record = ipRequests.get(ip);

  // Check if IP is currently blocked
  if (record.blockedUntil > now) {
    console.warn(`[RateLimit] Blocked request from ${ip}`);
    return res.status(429).json({
      error: 'Too many requests. Please wait before trying again.',
      retryAfter: Math.ceil((record.blockedUntil - now) / 1000)
    });
  }

  // Clean old requests outside the window
  record.requests = record.requests.filter(t => t > now - RATE_LIMIT_WINDOW);

  // Check if exceeded limit
  if (record.requests.length >= RATE_LIMIT_MAX) {
    console.warn(`[RateLimit] IP ${ip} exceeded limit (${RATE_LIMIT_MAX}/${RATE_LIMIT_WINDOW}ms). Blocking...`);
    record.blockedUntil = now + BLOCK_DURATION;
    return res.status(429).json({
      error: 'Rate limit exceeded. Request blocked for 10 seconds.',
      retryAfter: 10
    });
  }

  record.requests.push(now);
  next();
};

async function startServer() {
  app.use(cors());
  app.use(morgan('dev'));
  app.use(express.json({ limit: '10mb' }));
  app.use(rateLimiter);

  // API Routes
  app.use('/api/compute', computeRouter);

  // Install Python Dependencies
  try {
    console.log('Installing Python dependencies from requirements.txt...');
    const { execSync } = await import('child_process');
    try {
      execSync('pip3 install -r backend/requirements.txt', { stdio: 'inherit' });
    } catch (e) {
      console.log('pip3 failed, trying pip...');
      execSync('pip install -r backend/requirements.txt', { stdio: 'inherit' });
    }
  } catch (err) {
    console.error('Failed to install Python dependencies:', err);
  }

  // Start Python FastAPI background process
  const startPython = (cmd) => {
    console.log(`[Server] Attempting to start Python backend with command: ${cmd}`);
    const proc = spawn(cmd, ['-u', path.join(__dirname, '../backend/main.py')], { 
      shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1', PORT: '9999' }
    });
    
    proc.stdout.on('data', (data) => console.log(`[FastAPI]: ${data.toString().trim()}`));
    proc.stderr.on('data', (data) => console.error(`[FastAPI Error]: ${data.toString().trim()}`));
    
    proc.on('error', (err) => {
      console.error(`[Server] Failed to start Python (${cmd}):`, err);
      if (cmd === 'python3') {
        console.log('[Server] Falling back to "python"...');
        startPython('python');
      }
    });

    proc.on('exit', (code) => {
      console.log(`[Server] Python process (${cmd}) exited with code ${code}`);
      if (code !== 0) {
        console.log('[Server] Restarting Python backend in 5 seconds...');
        setTimeout(() => startPython(cmd), 5000);
      }
    });

    return proc;
  };

  startPython('python3');

  // Vite middleware for development
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      root: path.join(__dirname, '../frontend'),
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'frontend/dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
