import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { BookOpenText, CircleDashed, AlertCircle, CheckCircle2, FlaskConical, Sigma } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
const INTERNAL_STEP_PREFIXES = ['Studio Kernel:', 'Dispatching Sub-problem'];
const LOGIC_STEP_PREFIXES = ['Initializing ', 'Variables identified:', 'Performing ', 'Computing ', 'Evaluating ', 'Analyzing ', 'Resolving '];

const markdownComponents = {
  h1: ({ children }) => <h1 className="text-3xl font-black tracking-tighter mt-12 mb-8 text-white uppercase border-b-4 border-white pb-3">{children}</h1>,
  h2: ({ children }) => <h2 className="text-2xl font-black tracking-tight mt-10 mb-6 text-white uppercase">{children}</h2>,
  h3: ({ children }) => <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-blue-500 mt-12 mb-4 drop-shadow-[0_0_10px_rgba(59,130,246,0.3)]">{children}</h3>,
  h4: ({ children }) => <h4 className="text-xs font-black tracking-widest mt-8 mb-4 text-white/40 uppercase">{children}</h4>,
  p: ({ children }) => <p className="leading-relaxed text-white/90 mb-6 text-base font-medium">{children}</p>,
  ul: ({ children }) => <ul className="space-y-4 mb-8 pl-2">{children}</ul>,
  ol: ({ children }) => <ol className="space-y-4 mb-8 list-decimal pl-6">{children}</ol>,
  li: ({ children }) => (
    <li className="leading-relaxed text-white/90 pl-2">
      <div className="flex gap-3">
        <div className="mt-2.5 h-1 w-1 bg-white/20 shrink-0" />
        <div>{children}</div>
      </div>
    </li>
  ),
  strong: ({ children }) => <strong className="font-black text-white">{children}</strong>,
  code: ({ children }) => <code className="bg-white/5 px-2 py-0.5 rounded font-mono text-[0.9em] text-blue-300 border border-white/5 shadow-inner">{children}</code>,
  hr: () => <div className="my-12 border-t-2 border-white/5 border-dashed" />,
};

const isInternalStep = (step = '') => INTERNAL_STEP_PREFIXES.some(prefix => step.startsWith(prefix));
const isLogicStep = (step = '') => LOGIC_STEP_PREFIXES.some(prefix => step.startsWith(prefix));

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
      {/* ── Computational Sequence ── */}
      <AnimatePresence mode="popLayout">
        {visibleSteps.map((step, i) => {
          const isLogic = isLogicStep(step);
          
          return (
            <motion.div
              key={`step-${i}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className={`relative pl-12 pb-12 last:pb-4 ${isLogic ? 'opacity-30' : 'opacity-100'}`}
            >
              {/* Vertical Timeline Line */}
              <div className="absolute left-0 top-0 bottom-0 w-px bg-white/5" />
              <div className={`absolute left-[-4px] top-6 w-2 h-2 rounded-full border border-[#0b0b0b] ${isLogic ? 'bg-white/10' : 'bg-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.6)]'}`} />
              
              <div className={`markdown-content ${isLogic ? 'text-xs font-mono lowercase tracking-wider opacity-60' : 'text-lg font-serif'}`}>
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
