import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { CheckCircle2, CircleDashed, AlertCircle, FlaskConical } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

const markdownComponents = {
  h1: ({ children }) => <h1 className="text-xl font-black tracking-tight mt-2 mb-4">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-bold tracking-tight mt-6 mb-3">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-bold uppercase tracking-[0.2em] text-white/70 mt-5 mb-2">{children}</h3>,
  p: ({ children }) => <p className="leading-8 text-white/90 mb-4">{children}</p>,
  ul: ({ children }) => <ul className="space-y-2 mb-4">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-2 mb-4 list-decimal pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-7">{children}</li>,
  strong: ({ children }) => <strong className="text-white">{children}</strong>,
  code: ({ children }) => <code className="bg-white/10 px-1.5 py-0.5 rounded text-[0.95em]">{children}</code>,
};

export default function SolutionStream({ steps, final, error, isStreaming }) {
  const hasContent = steps.length > 0 || final || error;
  if (!hasContent) return null;

  return (
    <div className="space-y-8">
      {/* ── Step log ── */}
      {steps.length > 0 && (
        <div className="space-y-4">
          <p className="text-[9px] font-black uppercase tracking-[0.3em] text-white/30">
            Step By Step
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
                  className="flex items-start gap-4 group rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                >
                  <div className="mt-0.5 shrink-0">
                    <CheckCircle2
                    className={`w-4 h-4 transition-colors ${
                        isLast && isStreaming
                          ? 'text-white/60'
                          : 'text-white/30'
                      }`}
                    />
                  </div>
                  <div
                    className={`text-sm tracking-tight transition-colors ${
                      isLast && isStreaming ? 'text-white/90' : 'text-white/70'
                    } markdown-content`}
                  >
                    <ReactMarkdown 
                      remarkPlugins={[remarkMath]}
                      components={markdownComponents}
                      rehypePlugins={[rehypeKatex]}
                    >
                      {step}
                    </ReactMarkdown>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

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
            className="bg-white/5 border border-white/10 p-6 md:p-8 rounded-2xl shadow-2xl space-y-6 overflow-hidden"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <FlaskConical className="w-3.5 h-3.5 text-white/40" />
                <h4 className="text-[9px] font-black uppercase tracking-[0.3em] text-white/40">
                  Final Answer
                </h4>
              </div>
              <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-[8px] font-bold rounded uppercase tracking-wider">
                Verified
              </span>
            </div>

            <div className="text-sm md:text-base leading-relaxed text-white max-w-none math-render overflow-x-auto">
              <ReactMarkdown 
                remarkPlugins={[remarkMath]}
                components={markdownComponents}
                rehypePlugins={[rehypeKatex]}
              >
                {final}
              </ReactMarkdown>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
