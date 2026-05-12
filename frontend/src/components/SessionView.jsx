import React from 'react';
import SolutionStream from './SolutionStream';
import StudioCanvas from './StudioCanvas';
import UnitLens from './UnitLens';
import DataTable from './DataTable';

const SessionView = ({
  currentSteps,
  currentFinal,
  currentError,
  currentDiagrams,
  currentTables = [],
  currentUnits,
  isProcessing,
}) => {
  return (
    <div className="w-full max-w-5xl mx-auto pb-64 px-4">
      {/* ── Document Header ── */}
      <div className="mb-16 pt-12 relative">
          <div className="absolute -top-4 left-0 text-[10px] font-black tracking-[0.4em] text-blue-500/40 uppercase">Aeronautical & Mechanical Systems</div>
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b-2 border-white pb-6">
            <div className="space-y-2">
              <h1 className="text-4xl md:text-6xl font-black tracking-tighter uppercase leading-[0.8] text-white">STUDIO<br/>REPORT</h1>
              <div className="flex items-center gap-4 text-[10px] font-mono opacity-40 uppercase tracking-widest mt-4">
                <span>Kernel v2.4.0</span>
                <span>•</span>
                <span>Ref: MS-{Math.floor(Math.random()*10000)}</span>
                <span>•</span>
                <span>{new Date().toLocaleTimeString()}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
               <div className={`px-4 py-1.5 rounded-full text-[10px] font-black tracking-widest border transition-all ${isProcessing ? 'bg-blue-500/10 border-blue-500/40 text-blue-400 animate-pulse' : 'bg-green-500/10 border-green-500/40 text-green-400'}`}>
                 {isProcessing ? 'CALCULATING ENGINE' : 'VERIFIED STOCHASTIC ID'}
               </div>
               <div className="text-[10px] font-mono text-white/20 uppercase tracking-widest italic pt-2">Precision Level: NIST Traceable</div>
            </div>
          </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
        {/* Left Column: Logic & Results */}
        <div className="lg:col-span-12 space-y-20">
          
          {/* I. Methodology */}
          <section className="relative">
            <div className="sticky top-24 z-10 mb-8 bg-[#0b0b0b]/80 backdrop-blur-md py-2 border-b border-white/5">
               <h3 className="text-xs font-black uppercase tracking-[0.3em] text-white/30">I. Computational Sequence</h3>
            </div>
            <SolutionStream steps={currentSteps} final={null} error={currentError} isStreaming={isProcessing} />
          </section>

          {/* II. Visual Analytics */}
          {currentDiagrams.length > 0 && (
            <section>
              <div className="mb-8 border-b border-white/5 py-2">
                <h3 className="text-xs font-black uppercase tracking-[0.3em] text-white/30">II. Geometric Synthesis</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {currentDiagrams.map((diag, i) => (
                  <div key={i} className={currentDiagrams.length === 1 ? 'md:col-span-2' : ''}>
                    <StudioCanvas type={diag.diagram_type} data={diag.data} width={800} height={500} />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* III. Tabulated Data */}
          {currentTables.length > 0 && (
            <section>
               <div className="mb-8 border-b border-white/5 py-2">
                <h3 className="text-xs font-black uppercase tracking-[0.3em] text-white/30">III. Quantized Datasets</h3>
              </div>
              <div className="space-y-6">
                {currentTables.map((table, index) => (
                  <DataTable
                    key={`${table.title || 'table'}-${index}`}
                    data={table.rows || []}
                    columns={table.columns || []}
                    title={table.title}
                  />
                ))}
              </div>
            </section>
          )}

          {/* IV. Synthesis & Verification */}
          {currentFinal && (
            <section className="bg-white/[0.02] border border-white/10 rounded-[40px] p-8 md:p-12 relative overflow-hidden backdrop-blur-3xl shadow-2xl">
              <div className="absolute top-0 right-0 p-8 opacity-5">
                <div className="w-32 h-32 border-8 border-white rounded-full flex items-center justify-center font-black text-4xl">CERT</div>
              </div>
              
              <div className="mb-12">
                <h3 className="text-[10px] font-black uppercase tracking-[0.4em] text-blue-400 mb-2">IV. Validation Outcome</h3>
                <div className="h-px w-24 bg-blue-400/50" />
              </div>

              <SolutionStream steps={[]} final={currentFinal} error={null} isStreaming={false} />
              
              {currentUnits && currentUnits.length > 0 && (
                <div className="mt-12 pt-12 border-t border-white/5">
                  <UnitLens units={currentUnits} />
                </div>
              )}
              
              <div className="mt-16 flex items-center justify-between opacity-20 text-[8px] font-mono uppercase tracking-[0.5em]">
                <span>Kernel Instance S5-Alpha</span>
                <span>Deterministic Computation Layer</span>
                <span>AI Verified Logic</span>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

export default SessionView;
