import express from 'express';
import fetch from 'node-fetch';

const router = express.Router();

router.post('/', async (req, res) => {
    const payload = req.body;

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    try {
        const response = await fetch('http://127.0.0.1:9999/api/compute/solve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errBody = await response.text();
            console.error(`[Proxy] Backend Error (${response.status}):`, errBody);
            try {
                const jsonErr = JSON.parse(errBody);
                throw new Error(`Engine Error: ${jsonErr.error || jsonErr.message || errBody}`);
            } catch (e) {
                // If it's not JSON, it might be a generic error
                if (response.status === 404) throw new Error('Solver endpoint not found.');
                if (response.status === 502 || response.status === 503) throw new Error('Solver engine is currently starting or unavailable.');
                throw new Error(`Backend responded with ${response.status}: ${errBody.substring(0, 100)}`);
            }
        }

        // Stream the response properly using async iterator
        for await (const chunk of response.body) {
            res.write(chunk);
        }
        res.end();

    } catch (error) {
        console.error('Proxy Error:', error);
        res.write(`data: ${JSON.stringify({ type: 'error', message: error.message })}\n\n`);
        res.end();
    }
});

export default router;
