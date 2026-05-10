import express from 'express';
import fetch from 'node-fetch';

const router = express.Router();

router.post('/', async (req, res) => {
  const extractedData = req.body;

  try {
    // Proxy to local-mock or remote backend
    // In preview, we typically proxy to the Python backend running on localhost
    
    // Check if we should use the Python backend
    const API_BASE = process.env.VITE_BACKEND_URL;
    
    if (API_BASE) {
      const pythonResponse = await fetch(`${API_BASE}/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(extractedData)
      });
      pythonResponse.body.pipe(res);
    } else {
      // Default fallback for preview if no remote backend is specified
      // We assume the Python backend is running locally on port 8000 (starting from server/index.js)
      try {
        const pythonResponse = await fetch('http://localhost:8000/solve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(extractedData)
        });
        pythonResponse.body.pipe(res);
      } catch (err) {
        // Final fallback if local python is also unreachable
        res.setHeader('Content-Type', 'text/event-stream');
        res.write(`data: ${JSON.stringify({ type: 'step', content: 'Domain identified: ' + (extractedData.topic || 'unknown') })}\n\n`);
        res.write(`data: ${JSON.stringify({ type: 'step', content: 'Note: Solver backend unreachable. Check logs.' })}\n\n`);
        res.write(`data: ${JSON.stringify({ type: 'final', answer: 'Extraction complete (local solver offline).' })}\n\n`);
        res.end();
      }
    }

  } catch (error) {
    console.error('Computation Route Error:', error);
    res.status(500).json({ error: true, message: error.message });
  }
});

export default router;
