import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, CircleDashed, AlertCircle, FlaskConical } from 'lucide-react';

export default function SolutionStream({ steps, final, error, isStreaming }) {
  // `steps` is expected to be an array of strings (step log messages)
  // `final` is expected to be a string (the final answer text)
  // `error` is expected to be null or { message: string }
  // `isStreaming` boolean — true while SSE is still open

  const hasContent = steps.length > 0 || final || error;

  if (!hasContent) return null;

  return (
    <div className="space-y-6">

      {/* ── Step log ── */}
      {steps.length > 0 && (
        <div className="space-y-3">
          <p className="text-[9px] font-black uppercase tracking-[0.3em] text-white/30">
            Analysis Log
          </p>
          <AnimatePresence mode="popLayout">
            {steps.map((step, i) => {
              const isLast = i === steps.length - 1;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-start gap-3 group"
                >
                  <div className="mt-0.5 shrink-0">
                    <CheckCircle2
                      className={`w-3.5 h-3.5 transition-colors ${
                        isLast && isStreaming
                          ? 'text-white/60'
                          : 'text-white/30'
                      }`}
                    />
                  </div>
                  <p
                    className={`text-xs font-mono tracking-tight transition-colors ${
                      isLast && isStreaming ? 'text-white/80' : 'text-white/40'
                    }`}
                  >
                    {step}
                  </p>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {/* Spinner shown while streaming and no final answer yet */}
          {isStreaming && !final && !error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3 pl-0.5"
            >
              <CircleDashed className="w-3.5 h-3.5 text-white/20 animate-spin shrink-0" />
              <p className="text-xs font-mono text-white/20 uppercase tracking-widest">
                Processing Next Step...
              </p>
            </motion.div>
          )}
        </div>
      )}

      {/* ── Error panel ── */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="bg-red-500/10 border border-red-500/30 p-5 rounded-lg flex items-start gap-3"
          >
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <div className="space-y-1 min-w-0">
              <h4 className="text-[9px] font-black uppercase tracking-widest text-red-400">
                Operation Failed
              </h4>
              <p className="text-sm text-red-400/80 break-words">
                {error?.message ?? String(error)}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Final answer panel ── */}
      <AnimatePresence>
        {final && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="bg-white/5 border border-white/10 p-6 rounded-xl shadow-2xl space-y-4"
          >
            {/* Header row */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-3.5 h-3.5 text-white/40" />
                <h4 className="text-[9px] font-black uppercase tracking-[0.3em] text-white/40">
                  Final Solution
                </h4>
              </div>
              <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-[8px] font-bold rounded uppercase tracking-wider">
                Verified
              </span>
            </div>

            {/* Answer body — renders newlines and bold markdown simply */}
            <div className="space-y-2">
              {String(final)
                .split('\n')
                .map((line, i) => {
                  // Render **bold** markdown inline
                  const parts = line.split(/(\*\*[^*]+\*\*)/g);
                  return (
                    <p
                      key={i}
                      className={`font-mono leading-relaxed ${
                        line.startsWith('**')
                          ? 'text-sm text-green-400'
                          : 'text-xl font-black tracking-tight text-white'
                      }`}
                    >
                      {parts.map((part, j) =>
                        part.startsWith('**') && part.endsWith('**') ? (
                          <strong key={j} className="font-black">
                            {part.slice(2, -2)}
                          </strong>
                        ) : (
                          <span key={j}>{part}</span>
                        )
                      )}
                    </p>
                  );
                })}
            </div>

            {/* Source model badge if available */}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
