# Engineering Math Studio 🛠️📐

Engineering Math Studio is a cutting-edge computational workbench designed for engineers, students, and researchers. It provides a seamless interface to solve complex mathematical and structural engineering problems by combining the power of Large Language Models (LLMs) with specialized numerical and symbolic solver engines.

## 🚀 The Vision
Most engineering tools require rigid input formats or complex programming knowledge. Engineering Math Studio humanizes the process—allowing you to snap a photo of a beam diagram or describe a calculus problem in plain English, then transforming that input into rigorous, verified engineering data.

## ✨ Features

### 🖼️ Vision-to-Data Pipeline
- **Handwritten Problem Support:** Upload images of sketches, textbook problems, or handwritten notes.
- **Diagram Extraction:** Automated detection of material properties, load values, and geometric constraints.

### 🧠 Intelligent Solver Orchestration
The system automatically routes problems to the most qualified engine:
- **Structural Engine:** Finite Element Method (FEM) simulations for trusses, frames, and beams.
- **Symbolic Math Engine:** Powered by `SymPy` for exact algebraic solutions and calculus.
- **Numerical Compute Engine:** Powered by `NumPy` and `SciPy` for high-precision engineering approximations.

### 📊 Dynamic Technical Visualization
- **Live Canvas Rendering:** Interactive SVGs and Canvases for Bending Moment Diagrams (BMD), Axial Force (AFD), and Shear Force (SFD).
- **Step-by-Step Analysis:** Watch as the "AI Engine" break downs the problem into mechanical steps.

### 🛡️ Robust Architecture
- **Real-Time Streaming:** Leveraging Server-Sent Events (SSE) for zero-latency updates.
- **State Persistence:** Local-first history storage using IndexedDB.

## 🛠 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Interface** | React 18, Vite, Tailwind CSS, Motion (Animations) |
| **Logic (Proxy)** | Node.js (Express), Node-Fetch |
| **AI Extraction** | Google Gemini (Multi-modal Vision & Extraction) |
| **Compute Kernel** | Python (FastAPI), NumPy, SciPy, SymPy |

## 📦 Project Structure

```text
├── frontend/          # React SPA (Best for Vercel/Netlify)
│   ├── src/           # Component library and UI logic
│   └── public/        # Static assets
├── backend/           # Python FastAPI Core (Best for Render/Railway)
│   ├── solvers/       # Domain-specific Python algorithms
│   └── main.py        # API Entrypoint
└── README.md          # Project Documentation
```

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- A Google Gemini API Key

### Installation

1. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

2. **Backend:**
   ```bash
   cd backend
   pip install -r requirements.txt
   python main.py
   ```

## 📝 Compliance & Ethics
This tool is designed for educational and preliminary engineering analysis. Always verify critical safety calculations with professional-grade certified software (e.g., Ansys, SAP2000).

---
*Built for the next generation of engineers.*
