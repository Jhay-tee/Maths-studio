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
  compact = false
}) => {
  return (
    <div className={`w-full space-y-8 ${compact ? '' : 'max-w-6xl mx-auto pb-32'}`}>
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

      <div className={`grid grid-cols-1 ${compact ? '' : 'xl:grid-cols-[minmax(0,1.18fr)_minmax(320px,0.82fr)]'} gap-10 items-start`}>
        <div className="space-y-6">
          <SolutionStream steps={currentSteps} final={currentFinal} error={currentError} isStreaming={isProcessing} />
          {currentTables.length > 0 && (
            <div className="space-y-5">
              <h3 className="text-[10px] font-black uppercase tracking-[0.28em] text-white/30">Tables</h3>
              {currentTables.map((table, index) => (
                <DataTable
                  key={`${table.title || 'table'}-${index}`}
                  data={table.rows || []}
                  columns={table.columns || []}
                  title={table.title}
                />
              ))}
            </div>
          )}
        </div>

        {currentDiagrams.length > 0 && (
          <div className="space-y-5 xl:sticky xl:top-24">
            <h3 className="text-[10px] font-black uppercase tracking-[0.28em] text-white/30">Technical Visuals</h3>
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
