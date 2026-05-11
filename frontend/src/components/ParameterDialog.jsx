import React, { useState } from 'react';
import { motion } from 'motion/react';
import { AlertCircle, X } from 'lucide-react';

export default function ParameterDialog({ 
  isOpen, 
  missingParams, 
  onSubmit, 
  onCancel,
  problemDescription 
}) {
  const [values, setValues] = useState({});

  if (!isOpen) return null;

  const handleInputChange = (paramKey, value) => {
    setValues(prev => ({
      ...prev,
      [paramKey]: value
    }));
  };

  const handleSubmit = () => {
    onSubmit(values);
    setValues({});
  };

  const handleCancel = () => {
    onCancel();
    setValues({});
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="bg-[#1a1a1a] border border-white/10 rounded-2xl max-w-md w-full shadow-2xl"
      >
        <div className="p-6 border-b border-white/5 flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            <AlertCircle className="w-5 h-5 text-yellow-400 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-lg font-black uppercase tracking-tight text-white">
                Missing Parameters
              </h2>
              <p className="text-xs text-white/50 mt-1">
                The system needs additional values to solve this problem
              </p>
            </div>
          </div>
          <button
            onClick={handleCancel}
            className="p-1 hover:bg-white/10 rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
          {problemDescription && (
            <div className="bg-white/5 p-3 rounded-lg border border-white/5 mb-4">
              <p className="text-xs font-mono text-white/60">
                Problem: <span className="text-white/80">{problemDescription}</span>
              </p>
            </div>
          )}

          <div className="space-y-3">
            {missingParams.map((param) => (
              <div key={param.key} className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-white/40">
                  {param.label}
                  {param.unit && <span className="text-white/30"> ({param.unit})</span>}
                </label>
                <input
                  type="number"
                  placeholder={param.hint || `Enter ${param.label}`}
                  value={values[param.key] || ''}
                  onChange={(e) => handleInputChange(param.key, e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/20 focus:border-white/30 focus:ring-1 focus:ring-white/10 transition-all"
                />
                {param.hint && (
                  <p className="text-[9px] text-white/30 italic">{param.hint}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="p-6 bg-white/5 border-t border-white/5 flex gap-3">
          <button
            onClick={handleCancel}
            className="flex-1 px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-white font-bold text-sm uppercase tracking-wider transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={missingParams.some(p => !values[p.key])}
            className="flex-1 px-4 py-2.5 bg-white text-black hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-bold text-sm uppercase tracking-wider transition-all"
          >
            Continue
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
