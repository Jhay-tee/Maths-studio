import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Zap, X, CheckCircle2 } from 'lucide-react';

const METHOD_ICONS = {
  'Substitution Method': '🔄',
  'Elimination Method': '➖',
  'Graphical Method': '📈',
  'Matrix Method': '▦',
  "Cramer's Rule": '⊞',
  'Quadratic Formula': 'Δ',
  'Completing the Square': '□',
  'Factorization': '✕',
  'Method of Joints': '🔩',
  'Method of Sections': '✂️',
  'Virtual Work Method': '⚡',
  'Area Moment Method': '∫',
  'Direct Integration': '∫',
  'Integration by Parts': '∫',
  'Substitution (Calculus)': '∫',
  'Partial Fractions': '½',
  'Direct Stiffness': '▤',
  'Macaulay\'s Method': '〜',
  'Loss Calculation': '△',
};

const METHOD_DESCRIPTIONS = {
  'Substitution Method': 'Isolate one variable, substitute into the other equation',
  'Elimination Method': 'Multiply equations to cancel a variable, then solve',
  'Graphical Method': 'Plot both equations and find intersection point',
  'Matrix Method': 'Represent as Ax = b and solve using matrix inversion',
  "Cramer's Rule": 'Solve using determinants of the coefficient matrix',
  'Quadratic Formula': 'Apply x = (−b ± √(b²−4ac)) / 2a directly',
  'Completing the Square': 'Rewrite in vertex form to reveal roots',
  'Factorization': 'Factor the polynomial into linear/quadratic terms',
  'Method of Joints': 'Analyse forces at each joint in sequence',
  'Method of Sections': 'Cut the truss and apply equilibrium to a section',
  'Virtual Work Method': 'Apply principle of virtual displacements',
  'Area Moment Method': 'Use moment-area theorems for beam deflection',
  'Direct Integration': 'Integrate the load function stepwise',
  'Macaulay\'s Method': 'Use singularity functions for beam loading',
};

export default function MethodPopup({ isOpen, methods, domain, problemType, problemDescription, onSelect, onAutoSelect, onCancel, darkMode }) {
  const [selected, setSelected] = useState(null);

  if (!isOpen) return null;

  const bg = darkMode === false ? 'bg-white border-gray-200' : 'bg-[#1a1a1a] border-white/10';
  const headerBg = darkMode === false ? 'bg-gray-50 border-gray-100' : 'bg-white/5 border-white/5';
  const textCls = darkMode === false ? 'text-gray-900' : 'text-white';
  const mutedCls = darkMode === false ? 'text-gray-500' : 'text-white/50';
  const labelCls = darkMode === false ? 'text-gray-400' : 'text-white/30';
  const cardBase = darkMode === false
    ? 'border border-gray-200 bg-gray-50 hover:border-gray-400 hover:bg-gray-100'
    : 'border border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10';
  const cardSelected = darkMode === false
    ? 'border-blue-500 bg-blue-50'
    : 'border-blue-400/60 bg-blue-500/10';
  const cancelCls = darkMode === false
    ? 'bg-gray-100 hover:bg-gray-200 border border-gray-200 text-gray-700'
    : 'bg-white/5 hover:bg-white/10 border border-white/10 text-white';

  const handleContinue = () => {
    if (!selected) return;
    onSelect(selected);
    setSelected(null);
  };

  const handleAutoSelect = () => {
    onAutoSelect();
    setSelected(null);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0, y: 10 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.92, opacity: 0, y: 10 }}
        transition={{ type: 'spring', stiffness: 400, damping: 30 }}
        className={`${bg} border rounded-2xl max-w-xl w-full shadow-2xl overflow-hidden`}
      >
        <div className={`p-5 border-b ${headerBg} flex items-start justify-between gap-4`}>
          <div className="flex items-start gap-3 flex-1">
            <div className="w-8 h-8 rounded-lg bg-blue-400/10 border border-blue-400/20 flex items-center justify-center shrink-0 mt-0.5">
              <Zap className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <h2 className={`text-base font-black uppercase tracking-tight ${textCls}`}>Select Solution Method</h2>
              <p className={`text-xs mt-0.5 ${mutedCls}`}>
                Choose how you want this problem solved, or let the system decide.
              </p>
            </div>
          </div>
          <button onClick={onCancel} className={`p-1.5 rounded-lg hover:bg-white/10 transition-colors ${mutedCls}`}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
          {problemDescription && (
            <div className={`p-3 rounded-xl border ${darkMode === false ? 'bg-gray-50 border-gray-200' : 'bg-white/5 border-white/5'}`}>
              <p className={`text-[11px] font-mono ${mutedCls}`}>
                Problem: <span className={textCls}>{problemDescription}</span>
              </p>
            </div>
          )}

          <div>
            <p className={`text-[9px] font-black uppercase tracking-widest mb-3 ${labelCls}`}>Available Methods</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <AnimatePresence initial={false}>
                {(methods || []).map((method, idx) => {
                  const isSelected = selected === method;
                  return (
                    <motion.button
                      key={method}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      onClick={() => setSelected(method)}
                      className={`relative flex items-start gap-3 p-3.5 rounded-xl text-left transition-all ${isSelected ? cardSelected : cardBase}`}
                    >
                      <span className="text-lg leading-none shrink-0 mt-0.5">
                        {METHOD_ICONS[method] || '⚙️'}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className={`text-xs font-bold leading-tight ${textCls}`}>{method}</p>
                        {METHOD_DESCRIPTIONS[method] && (
                          <p className={`text-[10px] mt-1 leading-snug ${mutedCls}`}>{METHOD_DESCRIPTIONS[method]}</p>
                        )}
                      </div>
                      {isSelected && (
                        <CheckCircle2 className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
                      )}
                    </motion.button>
                  );
                })}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className={`p-5 border-t ${headerBg} flex gap-3`}>
          <button onClick={onCancel} className={`px-4 py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider transition-all ${cancelCls}`}>
            Cancel
          </button>
          <button
            onClick={handleAutoSelect}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider transition-all ${darkMode === false ? 'bg-gray-100 hover:bg-gray-200 border border-gray-200 text-gray-700' : 'bg-white/5 hover:bg-white/10 border border-white/10 text-white'}`}
          >
            <Zap className="w-4 h-4" /> Auto Select
          </button>
          <button
            onClick={handleContinue}
            disabled={!selected}
            className={`flex-1 px-4 py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider transition-all ${selected ? 'bg-white text-black hover:bg-gray-100' : 'bg-white/10 text-white/30 cursor-not-allowed'}`}
          >
            Continue →
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
