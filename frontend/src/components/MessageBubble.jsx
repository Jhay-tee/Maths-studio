import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Trash2, Copy, MoreVertical, Check } from 'lucide-react';
import useLongPress from '../lib/useLongPress';
import SessionView from './SessionView';

export default function MessageBubble({ msg, onDelete }) {
  const [showOptions, setShowOptions] = useState(false);
  const [copied, setCopied] = useState(false);

  const longPressProps = useLongPress(() => {
    if (window.navigator.vibrate) window.navigator.vibrate(50);
    setShowOptions(true);
  }, () => {}, { delay: 3000 });

  const handleCopy = (e) => {
    e.stopPropagation();
    const text = msg.content || msg.final || "";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => {
      setCopied(false);
      setShowOptions(false);
    }, 1500);
  };

  const isAssistant = msg.role === 'assistant';

  return (
    <div className={`flex flex-col ${isAssistant ? 'items-start' : 'items-end'} w-full group relative`}>
      <AnimatePresence>
        {showOptions && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 10 }}
            className="absolute z-50 bg-[#1a1a1a] border border-white/10 p-1.5 rounded-xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] flex items-center gap-1 -top-14"
          >
            <button 
              onClick={handleCopy}
              className="flex items-center gap-2 px-3 py-2 hover:bg-white/5 text-white rounded-lg transition-all text-[10px] font-black uppercase tracking-widest"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>

            <div className="w-px h-4 bg-white/10 mx-1" />

            <button 
              onMouseDown={(e) => e.stopPropagation()}
              onTouchStart={(e) => e.stopPropagation()}
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onDelete();
                setShowOptions(false);
              }}
              className="flex items-center gap-2 px-3 py-2 hover:bg-red-500/10 text-red-500 rounded-lg transition-all text-[10px] font-black uppercase tracking-widest"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div 
        {...longPressProps}
        className={`w-full max-w-[98%] md:max-w-[92%] transition-all duration-300 ${showOptions ? 'scale-[0.98] opacity-50 blur-[2px]' : ''}`}
      >
        {!isAssistant ? (
          <div className="flex flex-col items-end gap-2 max-w-[85%]">
            {msg.image && (
              <div className="rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
                <img src={`data:image/jpeg;base64,${msg.image}`} alt="User input" className="w-full h-auto max-h-[300px] object-contain bg-black/40" />
              </div>
            )}
            {msg.content && (
              <div className="bg-[#1a1a1a] border border-white/5 text-white/90 px-5 py-3 rounded-2xl shadow-sm font-medium text-sm leading-relaxed">
                {msg.content}
              </div>
            )}
          </div>
        ) : (
          <div className="w-full">
            <div className={`${msg.isProcessing ? 'opacity-85' : ''}`}>
              <SessionView 
                currentSteps={msg.steps || []}
                currentFinal={msg.final}
                currentError={msg.error}
                currentDiagrams={msg.diagrams || []}
                currentTables={msg.tables || []}
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
