import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';
import cors from 'cors';
import morgan from 'morgan';
import computeRouter from './routes/compute.js';
import { spawn } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(cors());
  app.use(morgan('dev'));
  app.use(express.json({ limit: '10mb' }));

  // API Routes
  app.use('/api/compute', computeRouter);

  // Start Python FastAPI background process
  // We specify the path to main.py
  const fastApiProcess = spawn('python3', [path.join(__dirname, '../backend/main.py')]);
  
  fastApiProcess.stdout.on('data', (data) => console.log(`[FastAPI]: ${data}`));
  fastApiProcess.stderr.on('data', (data) => console.error(`[FastAPI Error]: ${data}`));

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
