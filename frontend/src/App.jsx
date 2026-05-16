import React, { useState, useEffect, useRef, useCallback } from 'react';

const logger = {
  error: (msg, data) => console.error(`[Error] ${msg}`, data),
  warn: (msg, data) => console.warn(`[Warn] ${msg}`, data),
  info: (msg, data) => console.log(`[Info] ${msg}`, data),
};

import {
  History,
  Trash2,
  Sun,
  Moon,
  RotateCcw,
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

import HistorySidebar from './components/HistorySidebar';
import MessageBubble from './components/MessageBubble';
import ChatInput from './components/ChatInput';
import DocsPage from './components/DocsPage';
import ParameterDialog from './components/ParameterDialog';
import InputPopup from './components/InputPopup';
import MethodPopup from './components/MethodPopup';

// ── Helpers ──
const safeStringifyPayload = (value) => {
  const seen = new WeakSet();
  return JSON.stringify(value, (_key, val) => {
    if (val === null || val === undefined) return val;
    const t = typeof val;
    if (t === 'function' || t === 'symbol') return undefined;
    if (typeof Element !== 'undefined' && val instanceof Element) return undefined;
    if (typeof HTMLElement !== 'undefined' && val instanceof HTMLElement) return undefined;
    if (typeof SVGElement !== 'undefined' && val instanceof SVGElement) return undefined;
    if (t === 'object') {
      if (seen.has(val)) return undefined;
      seen.add(val);
      const maybeType = val && val.$$typeof;
      if (maybeType && typeof maybeType === 'string') return undefined;
    }
    return val;
  });
};

const makeAssistantMessage = (timestamp) => ({
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
});

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

  // ── Dark mode ──
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('studio-theme');
    return saved !== null ? saved === 'dark' : true;
  });

  // ── Existing param dialog ──
  const [showParamDialog, setShowParamDialog] = useState(false);
  const [missingParams, setMissingParams] = useState([]);
  const [pendingCompute, setPendingCompute] = useState(null);
  const [parameterPrompt, setParameterPrompt] = useState('');

  // ── Input popup (needs_input) ──
  const [showInputPopup, setShowInputPopup] = useState(false);
  const [inputPopupFields, setInputPopupFields] = useState([]);
  const [inputPopupDescription, setInputPopupDescription] = useState('');
  const [pendingInputContext, setPendingInputContext] = useState(null); // { saveContext }

  // ── Method popup (needs_method) ──
  const [showMethodPopup, setShowMethodPopup] = useState(false);
  const [methodPopupOptions, setMethodPopupOptions] = useState([]);
  const [methodPopupDescription, setMethodPopupDescription] = useState('');
  const [methodPopupDomain, setMethodPopupDomain] = useState('');
  const [pendingMethodContext, setPendingMethodContext] = useState(null); // { saveContext, assistantMessage, cachedRouting }

  // ── Retry ──
  const [lastPayload, setLastPayload] = useState(null);
  const [lastSaveContext, setLastSaveContext] = useState(null);

  const abortControllerRef = useRef(null);
  const scrollRef = useRef(null);
  const fileInputRef = useRef(null);

  // ── Theme application ──
  useEffect(() => {
    localStorage.setItem('studio-theme', darkMode ? 'dark' : 'light');
    if (darkMode) {
      document.body.classList.remove('light-mode');
    } else {
      document.body.classList.add('light-mode');
    }
  }, [darkMode]);

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
    if (messages.length > 0) {
      saveCurrentSession(messages);
    }
  }, [messages]);

  const loadSession = async () => {
    const saved = await loadCurrentSession();
    if (saved && Array.isArray(saved)) setMessages(saved);
  };

  const loadHistory = async () => {
    const data = await getHistory();
    setHistory(data.sort((a, b) => b.timestamp - a.timestamp));
  };

  const upsertMessage = (list, message) => {
    const index = list.findIndex(item => String(item.id) === String(message.id));
    if (index === -1) return [...list, message];
    const copy = [...list];
    copy[index] = { ...copy[index], ...message };
    return copy;
  };

  // ── Core SSE executor ──
  const executeCompute = useCallback(async ({ payload, assistantMessage, saveContext }) => {
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
    setShowInputPopup(false);
    setShowMethodPopup(false);

    setMessages(prev => {
      let next = upsertMessage(prev, userMessage);
      next = upsertMessage(next, assistantMessage);
      return next;
    });

    // Cache for retry
    setLastPayload(payload);
    setLastSaveContext(saveContext);

    const API_BASE = import.meta.env.VITE_BACKEND_URL || '';
    const endpoint = API_BASE ? `${API_BASE}/api/compute/solve` : '/api/compute/solve';

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: safeStringifyPayload(payload),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        setMessages(prev => prev.map(m => m.id === assistantMessage.id
          ? { ...m, error: { message: 'Failed to connect to engine.' }, isProcessing: false } : m));
        setIsProcessing(false);
        return;
      }

      if (!response.body) {
        setMessages(prev => prev.map(m => m.id === assistantMessage.id
          ? { ...m, error: { message: 'Engine returned no stream.' }, isProcessing: false } : m));
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

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          let data;
          try {
            data = JSON.parse(part.replace('data: ', ''));
          } catch {
            continue;
          }

          // ── needs_input event ──
          if (data.type === 'needs_input') {
            setMessages(prev => prev.map(m => m.id === assistantMessage.id
              ? { ...m, isProcessing: false, steps: [...m.steps, data.message || 'Please provide the missing input.'] }
              : m));
            setInputPopupFields(data.fields || []);
            setInputPopupDescription(data.problem_description || saveContext.currentInput);
            setPendingInputContext({ saveContext });
            setShowInputPopup(true);
            setIsProcessing(false);
            return;
          }

          // ── needs_method event ──
          if (data.type === 'needs_method') {
            setMessages(prev => prev.map(m => m.id === assistantMessage.id
              ? { ...m, isProcessing: false, steps: [...m.steps, 'Please select a solution method.'] }
              : m));
            setMethodPopupOptions(data.methods || []);
            setMethodPopupDescription(data.problem_description || saveContext.currentInput);
            setMethodPopupDomain(data.domain || '');
            setPendingMethodContext({
              saveContext,
              assistantMessage: { ...assistantMessage, isProcessing: true, steps: [], final: null, diagrams: [], tables: [], units: [] },
              cachedRouting: data.cached_routing || null,
            });
            setShowMethodPopup(true);
            setIsProcessing(false);
            return;
          }

          setMessages(prev => prev.map(msg => {
            if (msg.id !== assistantMessage.id) return msg;
            if (data.type === 'step') return { ...msg, steps: [...msg.steps, data.content] };
            if (data.type === 'table') return { ...msg, tables: [...(msg.tables || []), data] };
            if (data.type === 'units') return { ...msg, units: [...msg.units, ...data.data] };
            if (data.type === 'final') return { ...msg, final: (msg.final ? msg.final + '\n\n' : '') + data.answer };
            if (data.type === 'diagram') return { ...msg, diagrams: [...msg.diagrams, data] };
            if (data.type === 'needs_parameters') {
              setPendingCompute({ payload, assistantMessage, saveContext });
              setMissingParams(data.missing_params || []);
              setParameterPrompt(data.problem_description || saveContext.currentInput);
              setShowParamDialog(true);
              return { ...msg, isProcessing: false, steps: [...msg.steps, data.message || 'Parameter not specified.'] };
            }
            if (data.type === 'error') return { ...msg, error: { message: data.message }, isProcessing: false };
            return msg;
          }));
        }
      }

      setMessages(prev => {
        const finalMessages = prev.map(m => m.id === assistantMessage.id ? { ...m, isProcessing: false } : m);
        const finalAssistant = finalMessages.find(m => m.id === assistantMessage.id);
        if (finalAssistant) {
          saveComputation({
            type: 'Computation',
            title: saveContext.currentInput?.substring(0, 50) || 'Computation',
            topic: 'Engineering',
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
      logger.error('SSE/compute fetch failed:', error);
      const details = error?.message ? ` (${error.message})` : '';
      setMessages(prev => prev.map(m => m.id === assistantMessage.id
        ? { ...m, error: { message: `Connection interrupted.${details}` }, isProcessing: false } : m));
    } finally {
      setIsProcessing(false);
    }
  }, []);

  // ── Main compute trigger ──
  const handleCompute = useCallback(async (supplementalParams = null, existingPending = null) => {
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

    const assistantMessage = activePending?.assistantMessage || makeAssistantMessage(timestamp);

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
  }, [online, isProcessing, pendingCompute, inputText, imagePreview, dataFile, plotConfig, executeCompute]);

  // ── Handle Input Popup submit ──
  const handleInputPopupSubmit = useCallback((values, extraEquations) => {
    if (!pendingInputContext) return;
    const { saveContext } = pendingInputContext;

    // Reconstruct the input with the provided equations
    const eqParts = Object.values(values).filter(Boolean);
    const newInput = eqParts.join('; ');

    const timestamp = Date.now();
    const newSaveContext = {
      ...saveContext,
      currentInput: newInput,
      timestamp,
      userMessageId: timestamp.toString(),
    };
    const assistantMessage = makeAssistantMessage(timestamp);
    const payload = {
      type: 'text',
      input: newInput,
      plot_config: saveContext.currentConfig || {},
      supplemental_params: {},
      history: [],
    };

    setShowInputPopup(false);
    setPendingInputContext(null);
    setInputText('');

    executeCompute({ payload, assistantMessage, saveContext: newSaveContext });
  }, [pendingInputContext, executeCompute]);

  const handleInputPopupCancel = useCallback(() => {
    setShowInputPopup(false);
    setPendingInputContext(null);
    setIsProcessing(false);
  }, []);

  // ── Handle Method Popup select ──
  const handleMethodSelect = useCallback((method) => {
    if (!pendingMethodContext) return;
    const { saveContext, assistantMessage, cachedRouting } = pendingMethodContext;

    const payload = {
      type: 'text',
      input: saveContext.currentInput,
      plot_config: saveContext.currentConfig || {},
      supplemental_params: {},
      method: method,
      cached_routing: cachedRouting || null,
      history: [],
    };

    setShowMethodPopup(false);
    setPendingMethodContext(null);

    executeCompute({ payload, assistantMessage, saveContext });
  }, [pendingMethodContext, executeCompute]);

  const handleMethodAutoSelect = useCallback(() => {
    if (!pendingMethodContext) return;
    const { saveContext, assistantMessage, cachedRouting } = pendingMethodContext;

    const payload = {
      type: 'text',
      input: saveContext.currentInput,
      plot_config: saveContext.currentConfig || {},
      supplemental_params: {},
      method: 'auto',
      cached_routing: cachedRouting || null,
      history: [],
    };

    setShowMethodPopup(false);
    setPendingMethodContext(null);

    executeCompute({ payload, assistantMessage, saveContext });
  }, [pendingMethodContext, executeCompute]);

  const handleMethodPopupCancel = useCallback(() => {
    setShowMethodPopup(false);
    setPendingMethodContext(null);
    setIsProcessing(false);
  }, []);

  // ── Param dialog handlers ──
  const handleParameterSubmit = useCallback(async (values) => {
    if (!pendingCompute) return;
    await handleCompute(values, pendingCompute);
  }, [pendingCompute, handleCompute]);

  const handleParameterCancel = useCallback(() => {
    abortControllerRef.current?.abort();
    setPendingCompute(null);
    setShowParamDialog(false);
    setMissingParams([]);
    setParameterPrompt('');
    setIsProcessing(false);
  }, []);

  // ── Retry last computation ──
  const handleRetry = useCallback(async () => {
    if (!lastPayload || !lastSaveContext || isProcessing) return;
    const timestamp = Date.now();
    const assistantMessage = makeAssistantMessage(timestamp);
    await executeCompute({ payload: lastPayload, assistantMessage, saveContext: lastSaveContext });
  }, [lastPayload, lastSaveContext, isProcessing, executeCompute]);

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
      const lastIdx = [...copy].reverse().findIndex(msg => msg.role === 'assistant' && msg.isProcessing);
      if (lastIdx === -1) return prev;
      const actualIndex = copy.length - 1 - lastIdx;
      copy[actualIndex] = {
        ...copy[actualIndex],
        isProcessing: false,
        steps: [...(copy[actualIndex].steps || []), 'Calculation stopped by user.'],
      };
      return copy;
    });
  };

  // ── Theme classes ──
  const rootBg = darkMode ? 'bg-[#0b0b0b] text-white' : 'bg-[#f4f4f5] text-gray-900';
  const headerBg = darkMode ? 'bg-[#0b0b0b]/90 border-white/5' : 'bg-white/90 border-gray-200';
  const logoBox = darkMode ? 'bg-white text-black' : 'bg-gray-900 text-white';
  const iconBtn = darkMode ? 'hover:bg-white/5 text-white/60 hover:text-white' : 'hover:bg-gray-100 text-gray-500 hover:text-gray-900';
  const inputAreaBg = darkMode ? 'from-[#0b0b0b] via-[#0b0b0b]' : 'from-[#f4f4f5] via-[#f4f4f5]';
  const inputBoxBg = darkMode ? 'bg-[#1a1a1a]/90 border-white/10' : 'bg-white border-gray-200';
  const emptyCardBg = darkMode ? 'bg-white/5 border-white/5 hover:bg-white/10 hover:border-white/20' : 'bg-white border-gray-200 hover:border-gray-400 hover:shadow-sm';
  const emptyTextMuted = darkMode ? 'opacity-30' : 'text-gray-400';

  const TOPICS = [
    { label: "Simultaneous Eq", icon: "⊕", prompt: "Solve the simultaneous equations: " },
    { label: "Calculus", icon: "∫", prompt: "Analyze this Calculus problem: " },
    { label: "Structural", icon: "🏗️", prompt: "Analyze this Structural problem: " },
    { label: "Algebra", icon: "χ", prompt: "Solve this algebraic equation: " },
    { label: "Fluids", icon: "💧", prompt: "Analyze this Fluids problem: " },
    { label: "Thermodynamics", icon: "🔥", prompt: "Analyze this Thermodynamics problem: " },
    { label: "Mechanics", icon: "⚙️", prompt: "Analyze this Mechanics problem: " },
    { label: "Circuits", icon: "⚡", prompt: "Analyze this Circuits problem: " },
    { label: "Statistics", icon: "📊", prompt: "Analyze this Statistics problem: " },
  ];

  return (
    <div className={`min-h-screen flex flex-col font-sans selection:bg-white/20 transition-colors duration-300 ${rootBg}`}>

      {/* Header */}
      <header className={`px-5 py-4 border-b flex items-center justify-between sticky top-0 ${headerBg} backdrop-blur-md z-40`}>
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 flex items-center justify-center font-black rounded-lg text-sm ${logoBox}`}>M</div>
          <h1 className="text-[11px] font-black uppercase tracking-widest">MATHS STUDIO</h1>
          {!online && (
            <span className="text-[9px] font-black uppercase tracking-wider text-red-400 border border-red-400/30 px-2 py-0.5 rounded-full">Offline</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Retry */}
          {lastPayload && !isProcessing && (
            <button
              onClick={handleRetry}
              title="Retry last computation"
              className={`p-2 rounded-full transition-all ${iconBtn}`}
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
          {/* Dark/Light toggle */}
          <button
            onClick={() => setDarkMode(dm => !dm)}
            title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
            className={`p-2 rounded-full transition-all ${iconBtn}`}
          >
            {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <button onClick={clearChat} className={`p-2 rounded-full transition-all ${iconBtn}`}>
            <Trash2 className="w-4 h-4" />
          </button>
          <button onClick={() => setShowHistory(!showHistory)} className={`p-2 rounded-full transition-all ${iconBtn}`}>
            <History className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col relative">
        <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 p-4 md:p-8 space-y-8 scroll-smooth pb-52">
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="min-h-full flex flex-col items-center justify-center text-center px-4 py-12"
            >
              <div className={`w-16 h-16 md:w-20 md:h-20 flex items-center justify-center font-black rounded-2xl mb-6 shadow-2xl rotate-3 ${logoBox}`}>
                <span className="text-3xl md:text-4xl">M</span>
              </div>
              <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tighter mb-3 leading-none">
                Welcome to<br/>
                <span className={`text-transparent bg-clip-text bg-gradient-to-br ${darkMode ? 'from-white via-white to-white/20' : 'from-gray-900 via-gray-700 to-gray-400'}`}>
                  Maths Studio.
                </span>
              </h2>
              <p className={`text-[9px] md:text-xs font-mono uppercase tracking-[0.3em] md:tracking-[0.4em] mb-10 ${emptyTextMuted}`}>
                By Jhaytee • Precision Engineering Computing
              </p>

              <div className="grid grid-cols-3 gap-2.5 w-full max-w-xl mb-6">
                {TOPICS.map(topic => (
                  <button
                    key={topic.label}
                    onClick={() => setInputText(topic.prompt)}
                    className={`p-3 rounded-xl border transition-all text-left group ${emptyCardBg}`}
                  >
                    <span className="block text-lg mb-1.5 grayscale group-hover:grayscale-0 transition-all">{topic.icon}</span>
                    <span className={`text-[9px] font-black uppercase tracking-widest block ${darkMode ? '' : 'text-gray-700'}`}>{topic.label}</span>
                  </button>
                ))}
              </div>

              <p className={`text-[10px] font-mono max-w-sm ${emptyTextMuted}`}>
                Type a problem below, or select a topic above to get started. Supports text and image input.
              </p>
            </motion.div>
          ) : (
            messages.map(msg => (
              <MessageBubble
                key={msg.id}
                msg={msg}
                onDelete={() => deleteMessage(msg.id)}
                darkMode={darkMode}
              />
            ))
          )}
        </div>

        {/* Input area */}
        <div className={`fixed bottom-0 left-0 right-0 z-40 bg-gradient-to-t ${inputAreaBg} to-transparent pt-10 pb-5 px-4 md:px-8 pointer-events-none`}>
          <div className={`max-w-4xl mx-auto w-full pointer-events-auto border rounded-2xl p-2 shadow-2xl backdrop-blur-xl ${inputBoxBg}`}>
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
              darkMode={darkMode}
            />
          </div>
        </div>
      </main>

      {/* Sidebars & modals */}
      <AnimatePresence>
        {showHistory && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
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
        {showDocs && <DocsPage onClose={() => setShowDocs(false)} />}
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

      <AnimatePresence>
        {showInputPopup && (
          <InputPopup
            isOpen={showInputPopup}
            fields={inputPopupFields}
            problemDescription={inputPopupDescription}
            onSubmit={handleInputPopupSubmit}
            onCancel={handleInputPopupCancel}
            darkMode={darkMode}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showMethodPopup && (
          <MethodPopup
            isOpen={showMethodPopup}
            methods={methodPopupOptions}
            domain={methodPopupDomain}
            problemDescription={methodPopupDescription}
            onSelect={handleMethodSelect}
            onAutoSelect={handleMethodAutoSelect}
            onCancel={handleMethodPopupCancel}
            darkMode={darkMode}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
