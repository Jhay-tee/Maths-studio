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
    <div className="w-full max-w-4xl mx-auto pb-44 space-y-12">
      <header className="pt-8 pb-4 border-b border-white/5 flex items-end justify-between">
        <div className="space-y-1">
          <h2 className="text-3xl font-black tracking-tighter uppercase text-white/90">Technical Report</h2>
          <p className="text-[10px] font-mono opacity-30 uppercase tracking-[0.2em]">Generated via Compute Kernel • {new Date().toLocaleDateString()}</p>
        </div>
        <div className="text-[10px] font-mono flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded-full ${isProcessing ? 'bg-blue-500/10 text-blue-400 animate-pulse' : 'bg-green-500/10 text-green-400'}`}>
            {isProcessing ? 'SOLVING' : 'COMPLETED'}
          </span>
        </div>
      </header>

      {/* 1. Methodology & Steps */}
      <section className="space-y-6">
        <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest text-white/20">
          <div className="h-px flex-1 bg-white/5" />
          <span>I. Computational Sequence</span>
          <div className="h-px flex-1 bg-white/5" />
        </div>
        <SolutionStream steps={currentSteps} final={null} error={currentError} isStreaming={isProcessing} />
      </section>

      {/* 2. Graphical Analysis */}
      {currentDiagrams.length > 0 && (
        <section className="space-y-8 py-4">
          <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest text-white/20">
            <div className="h-px flex-1 bg-white/5" />
            <span>II. Graphical Analysis</span>
            <div className="h-px flex-1 bg-white/5" />
          </div>
          <div className="grid grid-cols-1 gap-8">
            {currentDiagrams.map((diag, i) => (
              <StudioCanvas key={i} type={diag.diagram_type} data={diag.data} width={800} height={400} />
            ))}
          </div>
        </section>
      )}

      {/* 3. Numerical Data */}
      {currentTables.length > 0 && (
        <section className="space-y-8 py-4">
          <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest text-white/20">
            <div className="h-px flex-1 bg-white/5" />
            <span>III. Tabulated Results</span>
            <div className="h-px flex-1 bg-white/5" />
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

      {/* 4. Final Verification */}
      {currentFinal && (
        <section className="space-y-8 pt-10 border-t-4 border-double border-white/5">
          <div className="flex items-center gap-4 text-[10px] font-black uppercase tracking-widest text-white/20">
            <div className="h-px flex-1 bg-white/5" />
            <span>IV. Synthesis & Verification</span>
            <div className="h-px flex-1 bg-white/5" />
          </div>
          <div className="bg-white/5 rounded-3xl p-8 border border-white/10 shadow-inner">
             <SolutionStream steps={[]} final={currentFinal} error={null} isStreaming={false} />
          </div>
          
          {currentUnits && currentUnits.length > 0 && (
            <div className="pt-8">
              <UnitLens units={currentUnits} />
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default SessionView;
