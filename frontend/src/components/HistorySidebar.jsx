import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  X, Info, Trash2, Plus, Book, Search, 
  Settings2, ChevronDown, Binary, 
  Activity, Layers, Droplets, FlaskConical,
  Zap, BarChart3, Ruler
} from 'lucide-react';

const TopicIcon = ({ topic = '' }) => {
  const t = topic.toLowerCase();
  if (t.includes('algebra')) return <Binary className="w-3.5 h-3.5 text-blue-400" />;
  if (t.includes('calculus')) return <Activity className="w-3.5 h-3.5 text-orange-400" />;
  if (t.includes('physics')) return <FlaskConical className="w-3.5 h-3.5 text-purple-400" />;
  if (t.includes('structural') || t.includes('beam')) return <Layers className="w-3.5 h-3.5 text-yellow-400" />;
  if (t.includes('fluids')) return <Droplets className="w-3.5 h-3.5 text-cyan-400" />;
  if (t.includes('circuit')) return <Zap className="w-3.5 h-3.5 text-green-400" />;
  if (t.includes('data') || t.includes('viz')) return <BarChart3 className="w-3.5 h-3.5 text-indigo-400" />;
  return <Ruler className="w-3.5 h-3.5 text-white/40" />;
};

const HistorySidebar = ({ history, setShowHistory, deleteHistoryItem, loadHistory, setMessages, setShowDocs }) => {
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('newest'); // 'newest' | 'oldest' | 'topic'

  const filteredHistory = useMemo(() => {
    let result = history.filter(item => 
      item.title?.toLowerCase().includes(search.toLowerCase()) || 
      item.topic?.toLowerCase().includes(search.toLowerCase())
    );

    if (sortBy === 'newest') result.sort((a, b) => b.timestamp - a.timestamp);
    if (sortBy === 'oldest') result.sort((a, b) => a.timestamp - b.timestamp);
    if (sortBy === 'topic') result.sort((a, b) => (a.topic || '').localeCompare(b.topic || ''));

    return result;
  }, [history, search, sortBy]);

  const startNew = () => {
    setMessages([]);
    setShowHistory(false);
  };

  const loadSession = (item) => {
    // Convert saved item (single-shot) to a message flow for the chat UI
    const mockUserMsg = {
      id: `h-user-${item.id}`,
      role: 'user',
      content: item.input || 'Archived Computation',
      timestamp: item.timestamp
    };
    const mockAsstMsg = {
      id: `h-asst-${item.id}`,
      role: 'assistant',
      steps: item.steps || [],
      final: item.final,
      diagrams: item.diagrams || [],
      units: item.units || [],
      timestamp: item.timestamp + 1000
    };
    setMessages([mockUserMsg, mockAsstMsg]);
    setShowHistory(false);
  };

  return (
    <motion.div 
      initial={{ x: '-100%' }}
      animate={{ x: 0 }}
      exit={{ x: '-100%' }}
      className="fixed inset-y-0 left-0 w-full sm:w-80 bg-[#111] border-r border-white/5 z-50 p-6 flex flex-col gap-6 shadow-2xl"
    >
      <div className="flex items-center justify-between">
        <h2 className="font-black uppercase tracking-widest text-[10px] opacity-40">System Archive</h2>
        <button onClick={() => setShowHistory(false)} className="hover:text-red-400 transition-colors"><X className="w-5 h-5"/></button>
      </div>

      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 opacity-20" />
          <input 
            type="text" 
            placeholder="Search archive..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white/5 border border-white/5 rounded-xl py-2.5 pl-10 pr-4 text-xs font-mono focus:outline-none focus:border-white/20 transition-all"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {['newest', 'oldest', 'topic'].map((sort) => (
            <button
              key={sort}
              onClick={() => setSortBy(sort)}
              className={`px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-widest border transition-all whitespace-nowrap ${sortBy === sort ? 'bg-white text-black border-white' : 'bg-transparent border-white/10 text-white/40 hover:border-white/30'}`}
            >
              {sort}
            </button>
          ))}
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-2 pr-2 scrollbar-hide">
        {filteredHistory.length === 0 && (
          <div className="text-center py-20 opacity-20">
            <Info className="w-8 h-8 mx-auto mb-2" />
            <p className="text-[10px] uppercase font-black tracking-widest">No entries found</p>
          </div>
        )}
        <AnimatePresence mode="popLayout">
          {filteredHistory.map((item) => (
            <motion.div
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              key={item.id}
              className="relative group lg:last:pb-8"
            >
              <button
                onClick={() => loadSession(item)}
                className="w-full text-left p-4 rounded-2xl border bg-white/[0.02] border-white/5 hover:border-white/20 hover:bg-white/5 transition-all flex items-start gap-4"
              >
                <div className="mt-1">
                  <TopicIcon topic={item.topic} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[9px] opacity-30 font-mono mb-1 flex items-center justify-between">
                    <span>{new Date(item.timestamp).toLocaleDateString()}</span>
                  </div>
                  <div className="text-xs font-bold truncate pr-6 uppercase tracking-tight text-white/80">{item.title}</div>
                  <div className="text-[9px] opacity-40 uppercase mt-1 truncate tracking-wider">
                    {item.topic} • {(item.diagrams || []).length} Diagrams
                  </div>
                </div>
              </button>
              <button 
                className="w-8 h-8 absolute right-2 top-1/2 -translate-y-1/2 flex items-center justify-center opacity-0 group-hover:opacity-100 hover:bg-red-500/10 hover:text-red-400 rounded-xl transition-all" 
                onClick={async (e) => {
                  e.stopPropagation();
                  if (window.confirm('Erase this computation from local history?')) {
                    await deleteHistoryItem?.(item.id);
                    loadHistory();
                  }
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      
      <button 
        onClick={startNew}
        className="w-full py-4 bg-white text-black font-black uppercase text-xs tracking-widest flex items-center justify-center gap-2 hover:bg-gray-200 transition-colors"
      >
        <Plus className="w-4 h-4" /> New Session
      </button>

      <button 
        onClick={() => { setShowDocs(true); setShowHistory(false); }}
        className="w-full py-3 bg-[#1a1a1a] text-white/60 hover:text-white border-t border-white/5 flex items-center justify-center gap-2 transition-all group"
      >
        <Book className="w-3.5 h-3.5 opacity-40 group-hover:opacity-100" /> 
        <span className="text-[10px] font-black uppercase tracking-widest">Docs & Capabilities</span>
      </button>
    </motion.div>
  );
};

export default HistorySidebar;
