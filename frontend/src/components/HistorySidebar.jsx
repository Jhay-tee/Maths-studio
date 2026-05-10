import React from 'react';
import { motion } from 'motion/react';
import { X, Info, Trash2, Plus } from 'lucide-react';

const HistorySidebar = ({ history, setActiveSession, setCurrentSteps, setCurrentFinal, setCurrentDiagrams, setCurrentUnits, setShowHistory, deleteHistoryItem, loadHistory, startNew }) => {
  return (
    <motion.div 
      initial={{ x: '-100%' }}
      animate={{ x: 0 }}
      exit={{ x: '-100%' }}
      className="fixed inset-y-0 left-0 w-full sm:w-80 bg-[#111] border-r border-white/5 z-50 p-6 flex flex-col gap-6 shadow-2xl"
      id="history-sidebar"
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
            onClick={() => {
              setActiveSession(item);
              setCurrentSteps(item.steps);
              setCurrentFinal(item.final);
              setCurrentDiagrams(item.diagrams);
              setCurrentUnits(item.units || []);
              setShowHistory(false);
            }}
            className="w-full text-left p-3 rounded bg-white/5 border border-white/5 hover:border-white/20 hover:bg-white/10 transition-all group"
          >
            <div className="text-[10px] opacity-40 font-mono mb-1">
              {new Date(item.timestamp).toLocaleDateString()}
            </div>
            <div className="text-xs font-bold truncate pr-6">{item.title}</div>
            <div className="text-[9px] opacity-40 uppercase mt-1 truncate">{JSON.stringify(item.diagrams.map(d => d.diagram_type))}</div>
            <Trash2 
              className="w-3 h-3 absolute right-3 top-3 opacity-0 group-hover:opacity-100 hover:text-red-400" 
              onClick={async (e) => {
                e.stopPropagation();
                await deleteHistoryItem(item.id);
                loadHistory();
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
