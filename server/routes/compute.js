import express from 'express';
import fetch from 'node-fetch';
import { GoogleGenAI } from '@google/genai';

const router = express.Router();

// Initialize Gemini for the Node.js preview bridge
const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const SYSTEM_INSTRUCTION = `
  You are a deterministic engineering input classifier. 
  YOUR ONLY TASK IS TO:
  1. Detect if the input is a valid Mathematics or Engineering problem.
  2. Classify the topic (Algebra, Calculus, Mechanics, Structural, etc.).
  3. Extract parameters into a clean JSON format for a Python solver.
  4. Detect if input is an image (handled by vision model) or text.
  5. Handle unit parsing:
     - Identify units like 'm', 'mm', 'cm', 'N', 'kN', 'lb', 'MPa', 'psi'.
     - Normalize all values to base SI units (Meters, Newtons, Pascals) for the 'value' fields in the JSON.
     - Include the original user string (e.g., "5kN") in a 'raw' field for each parameter if possible.

  STRICT RULES:
  - NO conversational behavior.
  - IF input is offensive, casual chat, or unrelated to engineering/math, return {"error": "not_math"}.
  - IF topic is unsupported, return {"error": "unsupported_topic"}.
  - Output ONLY valid JSON.
`;

router.post('/', async (req, res) => {
  const { input, type } = req.body;

  try {
    // 1. AI Extraction (Node.js version for preview)
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
    
    let aiParts;
    if (type === 'image') {
      aiParts = [
        { inlineData: { data: input, mimeType: "image/jpeg" } },
        { text: "Extract engineering parameters from this image for a solver engine. Output ONLY JSON." }
      ];
    } else {
      aiParts = [{ text: input }];
    }

    const result = await model.generateContent({
      contents: [{ role: 'user', parts: aiParts }],
      systemInstruction: SYSTEM_INSTRUCTION,
      generationConfig: { responseMimeType: 'application/json' }
    });

    const extractedData = JSON.parse(result.response.text());

    if (extractedData.error) {
       return res.status(400).json({
        error: true,
        type: extractedData.error === 'not_math' ? 'invalid_input' : 'unsupported_topic',
        message: extractedData.error === 'not_math' 
          ? "This is not a valid mathematics or engineering problem."
          : "This problem is outside supported engineering domains.",
      });
    }

    // 2. Proxy to local-mock or remote backend
    // If VITE_BACKEND_URL is not set, we try a mock response for the preview
    // or you can deploy your Render URL and put it in .env
    
    const API_BASE = process.env.VITE_BACKEND_URL;
    
    if (API_BASE) {
      const pythonResponse = await fetch(`${API_BASE}/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(extractedData)
      });
      pythonResponse.body.pipe(res);
    } else {
      // PREVIEW FALLBACK: If no Python backend is connected yet, return a mock success
      res.setHeader('Content-Type', 'text/event-stream');
      res.write(`data: ${JSON.stringify({ type: 'step', content: 'Domain identified: ' + extractedData.topic })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'step', content: 'Note: Local Python backend is not active in AI Studio preview. Deploy to Render to see full results.' })}\n\n`);
      res.write(`data: ${JSON.stringify({ type: 'final', answer: 'Preview Mode: AI Extraction complete.' })}\n\n`);
      res.end();
    }

  } catch (error) {
    console.error('Computation Route Error:', error);
    res.status(500).json({ error: true, message: error.message });
  }
});

export default router;
