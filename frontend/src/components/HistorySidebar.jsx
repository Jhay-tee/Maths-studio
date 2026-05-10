import React, { useState } from 'react';
import { motion } from 'motion/react';
import { X, Info, Trash2, Plus } from 'lucide-react';

const HistorySidebar = ({ history, setShowHistory, deleteHistoryItem, loadHistory, setMessages }) => {
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
      steps: item.steps,
      final: item.final,
      diagrams: item.diagrams,
      units: item.units,
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
        <h2 className="font-black uppercase tracking-widest text-xs">Past Computations</h2>
        <button onClick={() => setShowHistory(false)}><X className="w-5 h-5"/></button>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-hide">
        {history.length === 0 && (
          <div className="text-center py-20 opacity-30">
            <Info className="w-8 h-8 mx-auto mb-2" />
            <p className="text-xs uppercase font-mono">No history yet</p>
          </div>
        )}
        {history.map((item) => (
          <button
            key={item.id}
            onClick={() => loadSession(item)}
            className="w-full text-left p-4 rounded-sm border bg-white/5 border-white/5 hover:border-white/20 hover:bg-white/10 transition-all group relative"
          >
            <div className="text-[10px] opacity-40 font-mono mb-1">
              {new Date(item.timestamp).toLocaleDateString()}
            </div>
            <div className="text-xs font-bold truncate pr-6 uppercase tracking-tight">{item.title}</div>
            <div className="text-[9px] opacity-40 uppercase mt-1 truncate">
              {item.topic} | {item.diagrams.length} Diagrams
            </div>
            <Trash2 
              className="w-3 h-3 absolute right-4 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all" 
              onClick={async (e) => {
                e.stopPropagation();
                if (window.confirm('Delete computation?')) {
                  await deleteHistoryItem?.(item.id);
                  loadHistory();
                }
              }}
            />
          </button>
        ))}
      </div>
      
      <button 
        onClick={startNew}
        className="w-full py-4 bg-white text-black font-black uppercase text-xs tracking-widest flex items-center justify-center gap-2 hover:bg-gray-200 transition-colors"
      >
        <Plus className="w-4 h-4" /> New Session
      </button>
    </motion.div>
  );
};

export default HistorySidebar;
