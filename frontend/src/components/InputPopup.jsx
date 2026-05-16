import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertCircle, X, Plus, Trash2 } from 'lucide-react';

export default function InputPopup({ isOpen, fields, problemDescription, onSubmit, onCancel, darkMode }) {
  const [values, setValues] = useState({});
  const [extraEquations, setExtraEquations] = useState([]);

  if (!isOpen) return null;

  const isEquationMode = fields && fields.some(f => f.name && f.name.startsWith('equation'));

  const handleChange = (key, val) => {
    setValues(prev => ({ ...prev, [key]: val }));
  };

  const addEquation = () => {
    const idx = (fields ? fields.length : 2) + extraEquations.length + 1;
    setExtraEquations(prev => [...prev, { name: `equation_${idx}`, label: `Equation ${idx}`, placeholder: `e.g., enter equation ${idx}` }]);
  };

  const removeExtra = (name) => {
    setExtraEquations(prev => prev.filter(f => f.name !== name));
    setValues(prev => { const copy = { ...prev }; delete copy[name]; return copy; });
  };

  const allFields = [...(fields || []), ...extraEquations];

  const canSubmit = (fields || []).every(f => (values[f.name] || '').trim().length > 0);

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit(values, extraEquations.map(f => values[f.name]).filter(Boolean));
    setValues({});
    setExtraEquations([]);
  };

  const bg = darkMode === false ? 'bg-white border-gray-200' : 'bg-[#1a1a1a] border-white/10';
  const headerBg = darkMode === false ? 'bg-gray-50 border-gray-100' : 'bg-white/5 border-white/5';
  const inputCls = darkMode === false
    ? 'bg-gray-50 border border-gray-200 text-gray-900 placeholder:text-gray-400 focus:border-gray-400'
    : 'bg-white/5 border border-white/10 text-white placeholder:text-white/20 focus:border-white/30';
  const labelCls = darkMode === false ? 'text-gray-500' : 'text-white/40';
  const textCls = darkMode === false ? 'text-gray-900' : 'text-white';
  const mutedCls = darkMode === false ? 'text-gray-500' : 'text-white/50';
  const cancelCls = darkMode === false
    ? 'bg-gray-100 hover:bg-gray-200 border border-gray-200 text-gray-700'
    : 'bg-white/5 hover:bg-white/10 border border-white/10 text-white';
  const submitCls = canSubmit
    ? 'bg-white text-black hover:bg-gray-100'
    : 'bg-white/20 text-white/30 cursor-not-allowed';

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
        className={`${bg} border rounded-2xl max-w-lg w-full shadow-2xl overflow-hidden`}
      >
        <div className={`p-5 border-b ${headerBg} flex items-start justify-between gap-4`}>
          <div className="flex items-start gap-3 flex-1">
            <div className="w-8 h-8 rounded-lg bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center shrink-0 mt-0.5">
              <AlertCircle className="w-4 h-4 text-yellow-400" />
            </div>
            <div>
              <h2 className={`text-base font-black uppercase tracking-tight ${textCls}`}>Input Required</h2>
              <p className={`text-xs mt-0.5 ${mutedCls}`}>
                Please provide the missing values to proceed.
              </p>
            </div>
          </div>
          <button onClick={onCancel} className={`p-1.5 rounded-lg hover:bg-white/10 transition-colors ${mutedCls}`}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[55vh] overflow-y-auto">
          {problemDescription && (
            <div className={`p-3 rounded-xl border ${darkMode === false ? 'bg-gray-50 border-gray-200' : 'bg-white/5 border-white/5'}`}>
              <p className={`text-[11px] font-mono ${mutedCls}`}>
                Problem: <span className={textCls}>{problemDescription}</span>
              </p>
            </div>
          )}

          <div className="space-y-3">
            <AnimatePresence initial={false}>
              {allFields.map((field, idx) => (
                <motion.div
                  key={field.name}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <label className={`text-[10px] font-black uppercase tracking-widest ${labelCls}`}>
                      {field.label}
                      {field.required !== false && <span className="text-red-400 ml-1">*</span>}
                    </label>
                    {extraEquations.find(f => f.name === field.name) && (
                      <button onClick={() => removeExtra(field.name)} className="text-red-400/60 hover:text-red-400">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    placeholder={field.placeholder || `Enter ${field.label}`}
                    value={values[field.name] || ''}
                    onChange={e => handleChange(field.name, e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && canSubmit) handleSubmit(); }}
                    autoFocus={idx === 0}
                    className={`w-full rounded-xl px-4 py-2.5 text-sm focus:ring-1 focus:ring-white/10 transition-all outline-none font-mono ${inputCls}`}
                  />
                  {field.hint && (
                    <p className={`text-[9px] italic ${mutedCls}`}>{field.hint}</p>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {isEquationMode && (
              <button
                onClick={addEquation}
                className={`flex items-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all ${mutedCls} hover:opacity-80`}
              >
                <Plus className="w-3 h-3" /> Add another equation
              </button>
            )}
          </div>
        </div>

        <div className={`p-5 border-t ${headerBg} flex gap-3`}>
          <button onClick={onCancel} className={`flex-1 px-4 py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider transition-all ${cancelCls}`}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`flex-1 px-4 py-2.5 rounded-xl font-bold text-sm uppercase tracking-wider transition-all ${submitCls}`}
          >
            Continue →
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
