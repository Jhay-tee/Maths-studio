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

async function startServer() {
  app.use(cors());
  app.use(morgan('dev'));
  app.use(express.json({ limit: '10mb' }));

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
    console.log(`Attempting to start Python backend with: ${cmd}`);
    const proc = spawn(cmd, [path.join(__dirname, '../backend/main.py')], { shell: true });
    
    proc.stdout.on('data', (data) => console.log(`[FastAPI]: ${data}`));
    proc.stderr.on('data', (data) => console.error(`[FastAPI Error]: ${data}`));
    
    proc.on('error', (err) => {
      console.error(`Failed to start Python (${cmd}):`, err);
      if (cmd === 'python3') startPython('python');
    });

    proc.on('exit', (code) => {
      console.log(`Python process (${cmd}) exited with code ${code}`);
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
