import React, { useState, useEffect, useRef } from 'react';

const logger = {
  error: (msg, data) => console.error(`[Error] ${msg}`, data),
  warn: (msg, data) => console.warn(`[Warn] ${msg}`, data),
  info: (msg, data) => console.log(`[Info] ${msg}`, data),
};
import { 
  History, 
  Trash2
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  saveComputation, 
  getHistory, 
  deleteHistoryItem,
  saveCurrentSession,
  loadCurrentSession,
  clearCurrentSession
} from './lib/db';

// Modular Components (Eager Load)
import HistorySidebar from './components/HistorySidebar';
import MessageBubble from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import DocsPage from './components/DocsPage';
import ParameterDialog from './components/ParameterDialog';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [inputText, setInputText] = useState('');
  const [imagePreview, setImagePreview] = useState(null);
  const [dataFile, setDataFile] = useState(null);
  const [plotConfig, setPlotConfig] = useState({ type: 'line', title: '', xlabel: '', ylabel: '' });
  const [isProcessing, setIsProcessing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showDocs, setShowDocs] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  const [showParamDialog, setShowParamDialog] = useState(false);
  const [missingParams, setMissingParams] = useState([]);
  const [pendingCompute, setPendingCompute] = useState(null);
  const [parameterPrompt, setParameterPrompt] = useState('');
  const abortControllerRef = useRef(null);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    loadHistory();
    loadSession();
    const handleStatus = () => setOnline(navigator.onLine);
    window.addEventListener('online', handleStatus);
    window.addEventListener('offline', handleStatus);
    return () => {
      window.removeEventListener('online', handleStatus);
      window.removeEventListener('offline', handleStatus);
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    // Save current session whenever messages change
    if (messages.length > 0) {
      saveCurrentSession(messages);
    }
  }, [messages]);

  const loadSession = async () => {
    const saved = await loadCurrentSession();
    if (saved && Array.isArray(saved)) {
      setMessages(saved);
    }
  };

  const loadHistory = async () => {
    const data = await getHistory();
    setHistory(data.sort((a,b) => b.timestamp - a.timestamp));
  };

  const upsertMessage = (list, message) => {
    const index = list.findIndex(item => String(item.id) === String(message.id));
    if (index === -1) return [...list, message];
    const copy = [...list];
    copy[index] = { ...copy[index], ...message };
    return copy;
  };

  const executeCompute = async ({ payload, assistantMessage, saveContext }) => {
    abortControllerRef.current = new AbortController();
    const userMessage = {
      id: saveContext.userMessageId,
      role: 'user',
      content: saveContext.currentInput,
      image: saveContext.currentImage,
      timestamp: saveContext.timestamp
    };
    setIsProcessing(true);
    setShowParamDialog(false);
    setMissingParams([]);
    setParameterPrompt('');
    setMessages(prev => {
      let next = upsertMessage(prev, userMessage);
      next = upsertMessage(next, assistantMessage);
      return next;
    });

    const API_BASE = import.meta.env.VITE_BACKEND_URL || '';

    try {
      // Production has only FastAPI backend (no Express proxy server/).
      // FastAPI SSE endpoint:
      // POST /api/compute/solve
      const endpoint = API_BASE ? `${API_BASE}/api/compute/solve` : '/api/compute/solve';
      const safeStringifyPayload = (value) => {
        const seen = new WeakSet();
        return JSON.stringify(value, (_key, val) => {
          if (val === null || val === undefined) return val;

          const t = typeof val;
          if (t === 'function' || t === 'symbol') return undefined;

          // Drop DOM nodes / React internals if they ever get mixed into payload
          if (typeof Element !== 'undefined' && val instanceof Element) return undefined;
          if (typeof HTMLElement !== 'undefined' && val instanceof HTMLElement) return undefined;
          if (typeof SVGElement !== 'undefined' && val instanceof SVGElement) return undefined;

          if (t === 'object') {
            if (seen.has(val)) return undefined;
            seen.add(val);

            // React elements/fibers often have $$typeof; dropping is safest
            const maybeType = (val && val.$$typeof);
            if (maybeType && typeof maybeType === 'string') return undefined;
          }

          return val;
        });
      };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: safeStringifyPayload(payload),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, error: { message: 'Failed to connect to engine.' }, isProcessing: false } : m));
        setIsProcessing(false);
        return;
      }

      if (!response.body) {
        setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, error: { message: 'Engine returned no stream (SSE body missing).' }, isProcessing: false } : m));
        setIsProcessing(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let receivedFinal = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value);
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        parts.forEach(part => {
          if (part.startsWith('data: ')) {
            let data;
            try {
              data = JSON.parse(part.replace('data: ', ''));
            } catch (e) {
              // Don’t kill the SSE loop if we received an incomplete/malformed chunk.
              // Keep buffer logic intact and allow subsequent SSE events to arrive.
              return;
            }
            
            // Side effects for parameter collection must NOT be inside setMessages updater.
            if (data.type === 'needs_parameters') {
              setPendingCompute({ payload, assistantMessage, saveContext });
              setMissingParams(data.missing_params || []);
              setParameterPrompt(data.problem_description || saveContext.currentInput);
              setShowParamDialog(true);
            }

            const MAX_STEPS = 220; // prevents unbounded memory growth on long streams
            setMessages(prev => prev.map(msg => {
              if (msg.id !== assistantMessage.id) return msg;

              if (data.type === 'step') {
                const nextSteps = [...(msg.steps || []), data.content];
                return { ...msg, steps: nextSteps.length > MAX_STEPS ? nextSteps.slice(nextSteps.length - MAX_STEPS) : nextSteps };
              } else if (data.type === 'table') {
                return { ...msg, tables: [...(msg.tables || []), data] };
              } else if (data.type === 'units') {
                return { ...msg, units: [...msg.units, ...(data.data || [])] };
              } else if (data.type === 'final') {
                return { ...msg, final: (msg.final ? msg.final + '\n\n' : '') + data.answer };
              } else if (data.type === 'diagram') {
                return { ...msg, diagrams: [...msg.diagrams, data] };
              } else if (data.type === 'needs_parameters') {
                return {
                  ...msg,
                  isProcessing: false,
                  steps: [
                    ...(msg.steps || []),
                    data.message || 'Parameter is not specified.',
                  ],
                };
              } else if (data.type === 'error') {
                return { ...msg, error: { message: data.message }, isProcessing: false };
              }

              return msg;
            }));
          }
        });
      }

      setMessages(prev => {
        const finalMessages = prev.map(m => m.id === assistantMessage.id ? { ...m, isProcessing: false } : m);
        const finalAssistant = finalMessages.find(m => m.id === assistantMessage.id);
        if (finalAssistant) {
          saveComputation({
            type: 'Computation',
            title: saveContext.currentInput?.substring(0, 50) || 'Computation',
            topic: 'Engineering', // Can be enhanced to detect from routing
            input: saveContext.currentInput,
            result: finalAssistant.final,
            final: finalAssistant.final,
            steps: finalAssistant.steps || [],
            diagrams: finalAssistant.diagrams || [],
            tables: finalAssistant.tables || [],
            units: finalAssistant.units || [],
            image: saveContext.currentImage,
            timestamp: Date.now()
          }).then(() => loadHistory());
        }
        return finalMessages;
      });

    } catch (error) {
      if (error?.name === 'AbortError') return;
      console.error('SSE/compute fetch failed:', error);
      const details = error?.message ? ` (${error.message})` : '';
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, error: { message: `Connection interrupted.${details}` }, isProcessing: false } : m));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCompute = async (supplementalParams = null, existingPending = null) => {
    if (!online || isProcessing) return;

    const activePending = existingPending || pendingCompute;
    if (!activePending && !inputText.trim() && !imagePreview && !dataFile) return;

    const timestamp = Date.now();
    const saveContext = activePending?.saveContext || {
      timestamp,
      userMessageId: timestamp.toString(),
      currentInput: inputText,
      currentImage: imagePreview,
      currentData: dataFile,
      currentConfig: plotConfig,
    };

    const assistantMessage = activePending?.assistantMessage || {
      id: (timestamp + 1).toString(),
      role: 'assistant',
      isProcessing: true,
      steps: [],
      final: null,
      diagrams: [],
      tables: [],
      units: [],
      subProblems: {},
      timestamp,
    };

    const payload = {
      type: saveContext.currentImage ? 'image' : (saveContext.currentData ? 'data' : 'text'),
      input: saveContext.currentImage || (saveContext.currentData ? saveContext.currentData.base64 : saveContext.currentInput),
      filename: saveContext.currentData?.name,
      plot_config: saveContext.currentConfig,
      supplemental_params: supplementalParams || {},
      history: []
    };

    if (!activePending) {
      setInputText('');
      setImagePreview(null);
      setDataFile(null);
      setPlotConfig({ type: 'line', title: '', xlabel: '', ylabel: '' });
    }

    setPendingCompute(null);
    await executeCompute({ payload, assistantMessage, saveContext });
  };

  const handleParameterSubmit = async (values) => {
    if (!pendingCompute) return;
    await handleCompute(values, pendingCompute);
  };

  const handleParameterCancel = () => {
    abortControllerRef.current?.abort();
    setPendingCompute(null);
    setShowParamDialog(false);
    setMissingParams([]);
    setParameterPrompt('');
    setIsProcessing(false);
  };

  const deleteMessage = (id) => {
    setMessages(prev => prev.filter(m => String(m.id) !== String(id)));
  };

  const clearChat = async () => {
    if (window.confirm('Delete this session?')) {
      setMessages([]);
      await clearCurrentSession();
    }
  };

  const stopProcessing = () => {
    abortControllerRef.current?.abort();
    setIsProcessing(false);
    setMessages(prev => {
      const copy = [...prev];
      const lastAssistantIndex = [...copy].reverse().findIndex(msg => msg.role === 'assistant' && msg.isProcessing);
      if (lastAssistantIndex === -1) return prev;
      const actualIndex = copy.length - 1 - lastAssistantIndex;
      copy[actualIndex] = {
        ...copy[actualIndex],
        isProcessing: false,
        steps: [...(copy[actualIndex].steps || []), 'Calculation stopped by user.'],
      };
      return copy;
    });
  };

  return (
    <div className="min-h-screen bg-[#0b0b0b] text-white flex flex-col font-sans selection:bg-white/20">
      <header className="p-6 border-b border-white/5 flex items-center justify-between sticky top-0 bg-[#0b0b0b]/80 backdrop-blur-md z-40">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-black rounded-sm">M</div>
          <h1 className="text-xs font-black uppercase tracking-widest">MATHS STUDIO</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={clearChat} className="p-2 hover:bg-white/5 rounded-full"><Trash2 className="w-4 h-4 opacity-50" /></button>
          <button onClick={() => setShowHistory(!showHistory)} className="p-2 hover:bg-white/5 rounded-full"><History className="w-5 h-5" /></button>
        </div>
      </header>

      <main className="flex-1 overflow-hidden flex flex-col relative">
        <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 p-4 md:p-8 space-y-8 scroll-smooth pb-48">
          {messages.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="min-h-full flex flex-col items-center justify-center text-center px-4 py-12"
            >
              <div className="w-16 h-16 md:w-20 md:h-20 bg-white text-black flex items-center justify-center font-black rounded-2xl mb-6 shadow-2xl rotate-3">
                <span className="text-3xl md:text-4xl">M</span>
              </div>
              <h2 className="text-3xl md:text-6xl font-black uppercase tracking-tighter mb-4 leading-none">
                Welcome to<br/>
                <span className="text-transparent bg-clip-text bg-gradient-to-br from-white via-white to-white/20">Maths Studio.</span>
              </h2>
              <p className="text-[9px] md:text-xs font-mono opacity-30 uppercase tracking-[0.3em] md:tracking-[0.5em] mb-12 md:mb-16">
                By Jhaytee • Precision Engineering Computing
              </p>
              
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-2xl">
                {[
                  { label: "Structural", icon: "🏗️" },
                  { label: "Calculus", icon: "∫" },
                  { label: "Fluids", icon: "💧" },
                  { label: "Thermo", icon: "🔥" },
                  { label: "Mechanics", icon: "⚙️" },
                  { label: "Algebra", icon: "χ" }
                ].map(topic => (
                  <button 
                    key={topic.label}
                    onClick={() => setInputText(`Analyze this ${topic.label} problem: `)}
                    className="p-3 md:p-4 bg-white/5 border border-white/5 rounded-xl hover:bg-white/10 hover:border-white/20 transition-all text-left group"
                  >
                    <span className="block text-lg md:text-xl mb-2 grayscale group-hover:grayscale-0 transition-all">{topic.icon}</span>
                    <span className="text-[9px] md:text-[10px] font-black uppercase tracking-widest block">{topic.label}</span>
                  </button>
                ))}
              </div>
            </motion.div>
          ) : (
            messages.map((msg) => (
              <MessageBubble 
                key={msg.id} 
                msg={msg} 
                onDelete={() => deleteMessage(msg.id)} 
              />
            ))
          )}
        </div>

        <div className="fixed bottom-0 left-0 right-0 z-40 bg-gradient-to-t from-[#0b0b0b] via-[#0b0b0b] to-transparent pt-12 pb-6 px-4 md:px-8 pointer-events-none">
          <div className="max-w-4xl mx-auto w-full pointer-events-auto bg-[#1a1a1a]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-2 shadow-2xl">
            <ChatInput 
              inputText={inputText}
              setInputText={setInputText}
              imagePreview={imagePreview}
              setImagePreview={setImagePreview}
              dataFile={dataFile}
              setDataFile={setDataFile}
              plotConfig={plotConfig}
              setPlotConfig={setPlotConfig}
              handleCompute={handleCompute}
              isProcessing={isProcessing}
              fileInputRef={fileInputRef}
              onStop={stopProcessing}
            />
          </div>
        </div>
      </main>

      <AnimatePresence>
        {showHistory && (
          <>
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowHistory(false)}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden"
            />
            <HistorySidebar 
              history={history}
              loadHistory={loadHistory}
              setShowHistory={setShowHistory}
              setMessages={setMessages}
              deleteHistoryItem={deleteHistoryItem}
              setShowDocs={setShowDocs}
            />
          </>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showDocs && (
          <DocsPage onClose={() => setShowDocs(false)} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showParamDialog && (
          <ParameterDialog
            isOpen={showParamDialog}
            missingParams={missingParams}
            problemDescription={parameterPrompt}
            onSubmit={handleParameterSubmit}
            onCancel={handleParameterCancel}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
