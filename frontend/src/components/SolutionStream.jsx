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
    <div className="space-y-6">
      {/* ── Conversational Flow ── */}
      <AnimatePresence mode="popLayout">
        {visibleSteps.map((step, i) => (
          <motion.div
            key={`step-${i}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-white/80 leading-relaxed markdown-content prose prose-invert max-w-none prose-sm md:prose-base"
          >
            <ReactMarkdown 
              remarkPlugins={[remarkMath]}
              components={markdownComponents}
              rehypePlugins={[rehypeKatex]}
            >
              {step}
            </ReactMarkdown>
            {i < visibleSteps.length - 1 && <div className="h-px w-8 bg-white/5 my-6" />}
          </motion.div>
        ))}
      </AnimatePresence>

      {/* ── Final content (interleaved) ── */}
      <AnimatePresence>
        {visibleFinal && (
          <motion.div
            initial={{ opacity: 0, scale: 0.99 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-4 pt-6 border-t border-white/10"
          >
            <div className="flex items-center gap-2 mb-6">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-black uppercase tracking-widest text-emerald-400/60">Verified Result</span>
            </div>
            
            <div className="math-render text-white text-[15px] md:text-base leading-relaxed overflow-x-auto">
              <ReactMarkdown 
                remarkPlugins={[remarkMath]}
                components={markdownComponents}
                rehypePlugins={[rehypeKatex]}
              >
                {visibleFinal}
              </ReactMarkdown>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Status indicator ── */}
      {isStreaming && !visibleFinal && !error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center gap-3 py-4"
        >
          <div className="flex gap-1">
            <motion.div animate={{ scale: [1, 1.5, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0 }} className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <motion.div animate={{ scale: [1, 1.5, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <motion.div animate={{ scale: [1, 1.5, 1] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} className="h-1.5 w-1.5 rounded-full bg-white/20" />
          </div>
        </motion.div>
      )}

      {/* ── Error panel (Simplified) ── */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-500/5 rounded-2xl p-5 border border-red-500/20 text-red-400 text-sm flex gap-3"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error?.message ?? String(error)}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
