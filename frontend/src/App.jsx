import React, { useState, useEffect, useRef } from 'react';
import { 
  Plus, 
  History, 
  X,
  Trash2,
  Book
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
import SessionView from './components/SessionView';
import DocsPage from './components/DocsPage';

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

  const handleCompute = async () => {
    if (!online || isProcessing) return;
    if (!inputText.trim() && !imagePreview && !dataFile) return;

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputText,
      image: imagePreview,
      timestamp: Date.now()
    };

    const assistantMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      isProcessing: true,
      steps: [],
      final: null,
      diagrams: [],
      units: [],
      subProblems: {}, // For handling multiple solutions
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMessage, assistantMessage]);
    
    // Capture current values before clearing state
    const currentInput = inputText;
    const currentImage = imagePreview;
    const currentData = dataFile;
    const currentConfig = plotConfig;

    setInputText('');
    setImagePreview(null);
    setDataFile(null);
    setPlotConfig({ type: 'line', title: '', xlabel: '', ylabel: '' });
    setIsProcessing(true);

    abortControllerRef.current = new AbortController();

    const payload = {
      type: currentImage ? 'image' : (currentData ? 'data' : 'text'),
      input: currentImage || (currentData ? currentData.base64 : currentInput),
      filename: currentData?.name,
      plot_config: currentConfig,
      history: messages.slice(-4).map(m => ({ role: m.role, content: m.content || '' }))
    };

    const API_BASE = import.meta.env.VITE_BACKEND_URL || '';

    try {
      const endpoint = API_BASE ? `${API_BASE}/solve` : '/api/compute';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, error: { message: 'Failed to connect to engine.' }, isProcessing: false } : m));
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
            
            setMessages(prev => prev.map(msg => {
              if (msg.id !== assistantMessage.id) return msg;

              const pid = data.problem_id || 'default';
              const updatedSub = msg.subProblems[pid] || { steps: [], diagrams: [], units: [] };

              if (data.type === 'step') {
                return { ...msg, steps: [...msg.steps, data.content] };
              } else if (data.type === 'units') {
                return { ...msg, units: [...msg.units, ...data.data] };
              } else if (data.type === 'final') {
                return { ...msg, final: (msg.final ? msg.final + '\n\n' : '') + data.answer };
              } else if (data.type === 'diagram') {
                return { ...msg, diagrams: [...msg.diagrams, data] };
              } else if (data.type === 'error') {
                return { ...msg, error: { message: data.message } };
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
            input: currentInput,
            result: finalAssistant.final,
            steps: finalAssistant.steps,
            image: currentImage,
            timestamp: Date.now()
          }).then(() => loadHistory());
        }
        return finalMessages;
      });

    } catch (error) {
      if (error.name === 'AbortError') return;
      setMessages(prev => prev.map(m => m.id === assistantMessage.id ? { ...m, error: { message: 'Connection interrupted.' }, isProcessing: false } : m));
    } finally {
      setIsProcessing(false);
    }
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
        <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0 p-4 md:p-8 space-y-8 scroll-smooth pb-12">
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

        <div className="flex-shrink-0 p-4 md:p-8 bg-[#0b0b0b] border-t border-white/5 safe-bottom">
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
          />
          <div className="mt-4 text-center">
             <p className="text-[10px] md:text-xs font-mono opacity-20 uppercase tracking-tighter">
               Calculations are deterministic and verified by the kernel.
               <br/>
               <span className="opacity-50">Results are NOT generated by AI &bull; Cross-verify critical engineering values</span>
             </p>
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
    </div>
  );
}
