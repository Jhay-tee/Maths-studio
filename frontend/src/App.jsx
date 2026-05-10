import React, { useState, useEffect, useRef } from 'react';
import { 
  Plus, 
  History, 
  Plus as PlusIcon, 
  X
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { saveComputation, getHistory, deleteHistoryItem } from './lib/db';
// import { classifyProblem } from './lib/ai'; 

// Modular Components (Eager Load)
import HistorySidebar from './components/HistorySidebar';
import ProblemInput from './components/ProblemInput';
import SessionView from './components/SessionView';

export default function App() {
  const [activeSession, setActiveSession] = useState(null);
  const [history, setHistory] = useState([]);
  const [inputMode, setInputMode] = useState('text'); // 'text' | 'image'
  const [inputText, setInputText] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const abortControllerRef = useRef(null);

  // Stream state
  const [currentSteps, setCurrentSteps] = useState([]);
  const [currentFinal, setCurrentFinal] = useState(null);
  const [currentDiagrams, setCurrentDiagrams] = useState([]);
  const [currentError, setCurrentError] = useState(null);
  const [currentMeta, setCurrentMeta] = useState(null);
  const [currentUnits, setCurrentUnits] = useState([]);
  const [showFallbackBanner, setShowFallbackBanner] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    loadHistory();
    const handleStatus = () => setOnline(navigator.onLine);
    window.addEventListener('online', handleStatus);
    window.addEventListener('offline', handleStatus);
    return () => {
      window.removeEventListener('online', handleStatus);
      window.removeEventListener('offline', handleStatus);
    };
  }, []);

  const loadHistory = async () => {
    const data = await getHistory();
    setHistory(data.sort((a,b) => b.timestamp - a.timestamp));
  };

  const stopComputation = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsProcessing(false);
      setCurrentSteps(prev => [...prev, "Computation stopped by user."]);
    }
  };

  const handleCompute = async () => {
    if (!online) return;
    if (inputMode === 'text' && !inputText.trim()) return;
    if (inputMode === 'image' && !imagePreview) return;

    setIsProcessing(true);
    setCurrentSteps([]);
    setCurrentFinal(null);
    setCurrentDiagrams([]);
    setCurrentError(null);
    setCurrentUnits([]);

    abortControllerRef.current = new AbortController();

    const payload = {
      type: inputMode,
      input: inputMode === 'text' ? inputText : imagePreview
    };

    const API_BASE = import.meta.env.VITE_BACKEND_URL || '';

    try {
      // 1. Compute with raw input (Python handles AI extraction now)
      const endpoint = API_BASE ? `${API_BASE}/solve` : '/api/compute';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        const errData = await response.json();
        setCurrentError(errData);
        setIsProcessing(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value);
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        parts.forEach(part => {
          if (part.startsWith('data: ')) {
            const data = JSON.parse(part.replace('data: ', ''));
            if (data.type === 'step') {
              setCurrentSteps(prev => [...prev, data.content]);
            } else if (data.type === 'meta') {
              setCurrentMeta(data);
              if (data.is_fallback) {
                setShowFallbackBanner(true);
              }
            } else if (data.type === 'units') {
              setCurrentUnits(data.data);
            } else if (data.type === 'final') {
              setCurrentFinal(data.answer);
            } else if (data.type === 'diagram') {
              setCurrentDiagrams(prev => [...prev, data]);
            } else if (data.type === 'error') {
              setCurrentError({ type: 'system_error', message: data.message });
            }
          }
        });
      }

      // Save to IndexedDB when done
      if (!currentError) {
        const sessionTitle = currentMeta?.summary || (inputMode === 'text' ? inputText.substring(0, 30) : 'Image Computation');
        const sessionToSave = {
          title: sessionTitle,
          topic: currentMeta?.topic || 'general',
          input: inputMode === 'text' ? inputText : '[Image]',
          steps: currentSteps,
          final: currentFinal,
          diagrams: currentDiagrams,
          units: currentUnits
        };
        await saveComputation(sessionToSave);
        loadHistory();
      }

    } catch (error) {
      if (error.name === 'AbortError') return;
      setCurrentError({ type: 'network_error', message: 'Connection failed.' });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result.split(',')[1]);
      reader.readAsDataURL(file);
    }
  };

  const startNew = () => {
    setActiveSession(null);
    setCurrentSteps([]);
    setCurrentFinal(null);
    setCurrentDiagrams([]);
    setCurrentError(null);
    setCurrentUnits([]);
    setInputText('');
    setImagePreview(null);
    setShowHistory(false);
  };

  return (
    <div className="min-h-screen bg-[#0b0b0b] text-white flex flex-col font-sans selection:bg-white/20">
      <AnimatePresence>
        {showFallbackBanner && (
          <motion.div 
            initial={{ y: -100, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -100, opacity: 0 }}
            className="fixed top-24 left-1/2 -translate-x-1/2 z-[100] w-full max-w-md px-4 pointer-events-none"
          >
            <div className="bg-amber-500/10 border border-amber-500/50 backdrop-blur-xl px-4 py-3 rounded-full flex items-center justify-between shadow-2xl pointer-events-auto">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                <span className="text-[9px] font-black uppercase tracking-widest text-amber-500">
                  Engine Fallback Active: Running on {currentMeta?.model || 'Secondary Solver'}
                </span>
              </div>
              <button 
                onClick={() => setShowFallbackBanner(false)}
                className="p-1 hover:bg-amber-500/20 rounded-full transition-colors"
                id="close-fallback-btn"
              >
                <X className="w-3 h-3 text-amber-500" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="fixed bottom-4 left-4 z-50 text-[10px] font-mono uppercase tracking-[0.3em] opacity-40 mix-blend-difference">
        Made by Jhaytee
      </div>

      <header className="p-6 border-b border-white/5 flex items-center justify-between sticky top-0 bg-[#0b0b0b]/80 backdrop-blur-md z-40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white text-black flex items-center justify-center font-black rounded-sm shadow-[4px_4px_0px_rgba(255,255,255,0.2)]">
            M
          </div>
          <div>
            <h1 className="text-sm font-black uppercase tracking-widest">MATHS STUDIO</h1>
            <p className="text-[9px] font-mono opacity-50 uppercase">Engineering Computation v1.0</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {!online && (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-red-500/20 text-red-500 text-[10px] font-bold rounded-full border border-red-500/30">
              OFFLINE MODE
            </div>
          )}
          <button 
            onClick={() => setShowHistory(!showHistory)}
            className="p-2 hover:bg-white/5 rounded-full transition-colors flex items-center gap-2"
          >
            <History className="w-5 h-5" />
            <span className="text-xs font-bold uppercase tracking-tight hidden sm:inline">Archives</span>
          </button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        <AnimatePresence>
          {showHistory && (
              <HistorySidebar 
                history={history}
                setActiveSession={setActiveSession}
                setCurrentSteps={setCurrentSteps}
                setCurrentFinal={setCurrentFinal}
                setCurrentDiagrams={setCurrentDiagrams}
                setCurrentUnits={setCurrentUnits}
                setShowHistory={setShowHistory}
                deleteHistoryItem={deleteHistoryItem}
                loadHistory={loadHistory}
                startNew={startNew}
              />
          )}
        </AnimatePresence>

        <div className="flex-1 overflow-y-auto p-6 md:p-12 space-y-12">
            {(!currentSteps.length && !isProcessing && !activeSession) ? (
              <ProblemInput 
                inputMode={inputMode}
                setInputMode={setInputMode}
                inputText={inputText}
                setInputText={setInputText}
                imagePreview={imagePreview}
                setImagePreview={setImagePreview}
                handleCompute={handleCompute}
                stopComputation={stopComputation}
                isProcessing={isProcessing}
                online={online}
                fileInputRef={fileInputRef}
                handleImageUpload={handleImageUpload}
              />
            ) : (
              <>
                <SessionView 
                  currentSteps={currentSteps}
                  currentFinal={currentFinal}
                  currentError={currentError}
                  currentDiagrams={currentDiagrams}
                  currentUnits={currentUnits}
                  isProcessing={isProcessing}
                  currentMeta={currentMeta}
                />
                {!isProcessing && (
                  <div className="fixed bottom-12 left-1/2 -translate-x-1/2 flex items-center gap-4 p-2 bg-[#1a1a1a]/80 backdrop-blur-xl border border-white/10 rounded-full shadow-2xl z-50">
                    <button 
                      onClick={startNew}
                      className="px-6 py-3 bg-white text-black font-black uppercase text-[10px] tracking-widest rounded-full hover:bg-gray-200 transition-all flex items-center gap-2"
                    >
                      <PlusIcon className="w-4 h-4" /> New Session
                    </button>
                    <button 
                      onClick={() => setShowHistory(true)}
                      className="p-3 hover:bg-white/5 rounded-full transition-all"
                    >
                      <History className="w-5 h-5 text-white/60" />
                    </button>
                  </div>
                )}
              </>
            )}
        </div>
      </main>
    </div>
  );
}
