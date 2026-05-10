import React from 'react';
import SolutionStream from './SolutionStream';
import { Info } from 'lucide-react';
import StudioCanvas from './StudioCanvas';
import UnitLens from './UnitLens';

const SessionView = ({ currentSteps, currentFinal, currentError, currentDiagrams, currentUnits, isProcessing, currentMeta }) => {
  return (
    <div className="max-w-4xl mx-auto space-y-12 pb-32">
      <header className="space-y-4 border-l-2 border-white/20 pl-6">
        <div className="space-y-1">
          <h2 className="text-2xl font-black tracking-tight uppercase">Computation Studio</h2>
          {currentMeta?.topic && (
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-white text-black rounded-sm">
              <span className="text-[10px] font-black uppercase tracking-widest">{currentMeta.topic}</span>
            </div>
          )}
        </div>
        <div className="text-[10px] font-mono opacity-50 uppercase flex items-center gap-4">
          <span>{new Date().toLocaleString()}</span>
          <span>|</span>
          <span className="text-blue-400">STATUS: {isProcessing ? 'STREAMING' : 'COMPLETE'}</span>
        </div>
      </header>

      {currentUnits && currentUnits.length > 0 && (
        <UnitLens units={currentUnits} />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
        <div className="space-y-8">
          <div className="space-y-4">
            <h3 className="text-[11px] font-black uppercase tracking-widest text-white/40">Step-by-Step Solution</h3>
            <SolutionStream steps={currentSteps} final={currentFinal} error={currentError} />
          </div>
        </div>

        <div className="space-y-8">
          <h3 className="text-[11px] font-black uppercase tracking-widest text-white/40">Engineering Diagrams</h3>
          <div className="space-y-6">
            {currentDiagrams.map((diag, i) => (
              <StudioCanvas key={i} type={diag.diagram_type} data={diag.data} />
            ))}
            {!currentDiagrams.length && !isProcessing && (
              <div className="aspect-video border border-white/5 bg-white/5 rounded-lg flex flex-col items-center justify-center opacity-20">
                <Info className="w-10 h-10 mb-2" />
                <p className="text-xs font-mono uppercase tracking-widest">No diagrams for this topic</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SessionView;
