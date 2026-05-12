import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { BookOpenText, CircleDashed, AlertCircle, CheckCircle2, FlaskConical, Sigma } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
const INTERNAL_STEP_PREFIXES = ['Studio Kernel:', 'Dispatching Sub-problem', 'Initializing '];

const markdownComponents = {
  h1: ({ children }) => <h1 className="text-2xl font-black tracking-tight mt-2 mb-5 text-white">{children}</h1>,
  h2: ({ children }) => <h2 className="text-xl font-bold tracking-tight mt-8 mb-4 text-white">{children}</h2>,
  h3: ({ children }) => <h3 className="text-[11px] font-black uppercase tracking-[0.24em] text-white/55 mt-7 mb-3">{children}</h3>,
  h4: ({ children }) => <h4 className="text-sm font-semibold tracking-wide mt-5 mb-2 text-white/90">{children}</h4>,
  p: ({ children }) => <p className="leading-8 text-white/88 mb-5">{children}</p>,
  ul: ({ children }) => <ul className="space-y-3 mb-5 pl-1">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-3 mb-5 list-decimal pl-6">{children}</ol>,
  li: ({ children }) => <li className="leading-7 text-white/88 pl-1">{children}</li>,
  strong: ({ children }) => <strong className="text-white">{children}</strong>,
  code: ({ children }) => <code className="bg-white/10 px-1.5 py-0.5 rounded text-[0.95em] text-white">{children}</code>,
  hr: () => <div className="my-6 border-t border-white/10" />,
};

const isInternalStep = (step = '') => INTERNAL_STEP_PREFIXES.some(prefix => step.startsWith(prefix));

const sanitizeSteps = (steps = []) => {
  const seen = new Set();
  return steps.filter(step => {
    if (!step || isInternalStep(step) || seen.has(step)) return false;
    seen.add(step);
    return true;
  });
};

const sanitizeFinal = (final) => {
  if (!final) return final;
  return final
    .split('\n')
    .filter(line => !line.includes('**Method Used:**'))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};

export default function SolutionStream({ steps, final, error, isStreaming }) {
  const visibleSteps = sanitizeSteps(steps);
  const visibleFinal = sanitizeFinal(final);
  const hasContent = visibleSteps.length > 0 || visibleFinal || error;
  if (!hasContent) return null;

  return (
    <div className="space-y-8">
      {/* ── Step log ── */}
      {visibleSteps.length > 0 && (
        <div className="space-y-5">
          <div className="flex items-center gap-2 text-white/35">
            <BookOpenText className="w-4 h-4" />
            <p className="text-[10px] font-black uppercase tracking-[0.3em]">
              Step By Step
            </p>
          </div>
          <AnimatePresence mode="popLayout">
            {visibleSteps.map((step, i) => {
              const isLast = i === visibleSteps.length - 1;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-start gap-4 group rounded-3xl border border-white/10 bg-gradient-to-br from-white/[0.06] to-white/[0.02] px-5 py-4 shadow-[0_20px_60px_rgba(0,0,0,0.18)]"
                >
                  <div className="mt-0.5 shrink-0 flex items-center gap-3">
                    <div className={`flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-black ${
                      isLast && isStreaming ? 'border-blue-400/40 bg-blue-400/10 text-blue-200' : 'border-white/10 bg-white/5 text-white/55'
                    }`}>
                      {i + 1}
                    </div>
                  </div>
                  <div
                    className={`text-sm tracking-tight transition-colors ${
                      isLast && isStreaming ? 'text-white/94' : 'text-white/76'
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

          {isStreaming && !visibleFinal && !error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3 pl-1"
            >
              <CircleDashed className="w-4 h-4 text-blue-300/50 animate-spin shrink-0" />
              <p className="text-[11px] font-mono text-white/35 uppercase tracking-[0.28em]">
                Processing
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
            className="bg-red-500/10 border border-red-500/25 p-5 rounded-3xl flex items-start gap-3 shadow-[0_12px_40px_rgba(127,29,29,0.18)]"
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
        {visibleFinal && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] border border-white/10 p-6 md:p-9 rounded-[2rem] shadow-[0_24px_80px_rgba(0,0,0,0.24)] space-y-7 overflow-hidden"
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/12 border border-emerald-400/20">
                  <Sigma className="w-4 h-4 text-emerald-300/80" />
                </div>
                <div>
                  <h4 className="text-[10px] font-black uppercase tracking-[0.28em] text-white/45">
                    Final Answer
                  </h4>
                  <p className="text-sm text-white/55 mt-1">Clean result with the main working and conclusion.</p>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" />
                <span className="text-[9px] font-bold uppercase tracking-[0.22em] text-emerald-300">
                  Verified
                </span>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-white/8 bg-black/15 p-5 md:p-6">
              <div className="text-[15px] md:text-base leading-relaxed text-white max-w-none math-render overflow-x-auto">
                <ReactMarkdown 
                  remarkPlugins={[remarkMath]}
                  components={markdownComponents}
                  rehypePlugins={[rehypeKatex]}
                >
                  {visibleFinal}
                </ReactMarkdown>
              </div>
            </div>

            {!error && !isStreaming && (
              <div className="flex items-center gap-2 text-white/35">
                <FlaskConical className="w-3.5 h-3.5" />
                <span className="text-[10px] uppercase tracking-[0.22em]">Solver output completed</span>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
