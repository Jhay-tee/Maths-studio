import React from 'react';
import SolutionStream from './SolutionStream';
import { Info } from 'lucide-react';
import StudioCanvas from './StudioCanvas';
import UnitLens from './UnitLens';

const SessionView = ({ currentSteps, currentFinal, currentError, currentDiagrams, currentUnits, isProcessing, compact = false }) => {
  return (
    <div className={`w-full space-y-6 ${compact ? '' : 'max-w-4xl mx-auto pb-32'}`}>
      {!compact && (
        <header className="space-y-4 border-l-2 border-white/20 pl-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-black tracking-tight uppercase">Computation Studio</h2>
          </div>
          <div className="text-[10px] font-mono opacity-50 uppercase flex items-center gap-4">
            <span>{new Date().toLocaleString()}</span>
            <span>|</span>
            <span className="text-blue-400">STATUS: {isProcessing ? 'STREAMING' : 'COMPLETE'}</span>
          </div>
        </header>
      )}

      {currentUnits && currentUnits.length > 0 && (
        <UnitLens units={currentUnits} />
      )}

      <div className={`grid grid-cols-1 ${compact ? '' : 'lg:grid-cols-2'} gap-8 items-start`}>
        <div className="space-y-4">
          <h3 className="text-[10px] font-black uppercase tracking-widest text-white/30">Analysis Log</h3>
          <SolutionStream steps={currentSteps} final={currentFinal} error={currentError} />
        </div>

        {currentDiagrams.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-[10px] font-black uppercase tracking-widest text-white/30">Technical Visuals</h3>
            <div className="space-y-6">
              {currentDiagrams.map((diag, i) => (
                <StudioCanvas key={i} type={diag.diagram_type} data={diag.data} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SessionView;
