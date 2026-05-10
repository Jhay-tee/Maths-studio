import express from 'express';
import fetch from 'node-fetch';

const router = express.Router();

router.post('/', async (req, res) => {
    const payload = req.body;

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    try {
        const response = await fetch('http://localhost:9999/solve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errBody = await response.text();
            console.error(`Backend Error (${response.status}):`, errBody);
            try {
                const jsonErr = JSON.parse(errBody);
                throw new Error(`Engine Error: ${jsonErr.error || jsonErr.message || errBody}`);
            } catch (e) {
                throw new Error(`Backend responded with ${response.status}: ${errBody}`);
            }
        }

        // Pipe the streaming response from Python to the client
        response.body.pipe(res);

    } catch (error) {
        console.error('Proxy Error:', error);
        res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
        res.end();
    }
});

export default router;
