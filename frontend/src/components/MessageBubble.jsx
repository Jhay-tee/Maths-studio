import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Trash2, MoreVertical } from 'lucide-react';
import useLongPress from '../lib/useLongPress';
import SessionView from './SessionView';

export default function MessageBubble({ msg, onDelete }) {
  const [showOptions, setShowOptions] = useState(false);

  const longPressProps = useLongPress(() => {
    setShowOptions(true);
  }, () => {});

  const isAssistant = msg.role === 'assistant';

  return (
    <div className={`flex flex-col ${isAssistant ? 'items-start' : 'items-end'} w-full group relative`}>
      <AnimatePresence>
        {showOptions && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="absolute z-50 bg-[#1a1a1a] border border-white/10 p-1 rounded-lg shadow-2xl flex items-center gap-1 -top-12"
          >
            <button 
              onMouseDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete();
                setShowOptions(false);
              }}
              className="flex items-center gap-2 px-3 py-2 hover:bg-red-500/10 text-red-500 rounded-md transition-all text-[10px] font-black uppercase tracking-widest"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
            <button 
              onClick={() => setShowOptions(false)}
              className="px-3 py-2 hover:bg-white/5 text-white/40 rounded-md text-[10px] font-black uppercase"
            >
              Cancel
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div 
        {...longPressProps}
        className={`max-w-[85%] md:max-w-[70%] transition-all duration-300 ${showOptions ? 'scale-[0.98] opacity-50' : ''}`}
      >
        {!isAssistant ? (
          <div className="space-y-2">
            {msg.image && (
              <div className="rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
                <img src={`data:image/jpeg;base64,${msg.image}`} alt="User input" className="w-full h-auto max-h-[300px] object-contain bg-black/40" />
              </div>
            )}
            {msg.content && (
              <div className="bg-white text-black p-4 rounded-2xl rounded-tr-sm shadow-xl font-medium text-sm leading-relaxed">
                {msg.content}
              </div>
            )}
          </div>
        ) : (
          <div className="w-full">
            <div className={`p-1 rounded-2xl ${msg.isProcessing ? 'animate-pulse opacity-60' : ''}`}>
              <SessionView 
                currentSteps={msg.steps || []}
                currentFinal={msg.final}
                currentError={msg.error}
                currentDiagrams={msg.diagrams || []}
                currentUnits={msg.units || []}
                isProcessing={msg.isProcessing}
                compact={true}
              />
            </div>
          </div>
        )}
      </div>
      
      <div className="mt-1 px-1 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <span className="text-[9px] font-mono opacity-20 uppercase tracking-widest">
          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
        <button 
          onClick={() => setShowOptions(!showOptions)}
          className="text-white/20 hover:text-white transition-colors"
        >
          <MoreVertical className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
