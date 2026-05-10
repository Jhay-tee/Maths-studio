import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, CircleDashed, AlertCircle } from 'lucide-react';

export default function SolutionStream({ steps, final, error }) {
  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <AnimatePresence mode="popLayout">
          {steps.map((step, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-start gap-4 group"
            >
              <div className="mt-1">
                <CheckCircle2 className="w-4 h-4 text-white/40 group-last:text-white transition-colors" />
              </div>
              <p className="text-sm font-mono text-white/60 group-last:text-white transition-colors tracking-tight">
                {step}
              </p>
            </motion.div>
          ))}
        </AnimatePresence>
        
        {(!final && !error && steps.length > 0) && (
          <div className="flex items-center gap-4 animate-pulse">
            <CircleDashed className="w-4 h-4 text-white/20 animate-spin" />
            <p className="text-sm font-mono text-white/20 uppercase tracking-widest">
              Processing Next Step...
            </p>
          </div>
        )}
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-red-500/10 border border-red-500/50 p-6 rounded flex items-start gap-4"
        >
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-1" />
          <div className="space-y-1">
            <h4 className="text-xs font-black uppercase tracking-widest text-red-500">Operation Failed</h4>
            <p className="text-sm text-red-500/80">{error.message}</p>
          </div>
        </motion.div>
      )}

      {final && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white/5 border border-white/10 p-8 rounded shadow-2xl space-y-4"
        >
          <div className="flex items-center justify-between">
            <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/40">Final Solution</h4>
            <div className="px-2 py-0.5 bg-green-500/20 text-green-400 text-[8px] font-bold rounded uppercase">Verified</div>
          </div>
          <div className="text-2xl font-black tracking-tight leading-tight">
            {final}
          </div>
        </motion.div>
      )}
    </div>
  );
}
