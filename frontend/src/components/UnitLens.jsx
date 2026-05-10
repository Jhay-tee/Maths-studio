import React from 'react';
import { Ruler, Zap, Hash, Repeat, AlertTriangle } from 'lucide-react';

const CONVERSIONS = {
  force: (val) => [
    { label: 'N', value: val },
    { label: 'kN', value: val / 1000 },
    { label: 'MN', value: val / 1000000 },
    { label: 'lbf', value: val * 0.224809 },
  ],
  length: (val) => [
    { label: 'm', value: val },
    { label: 'cm', value: val * 100 },
    { label: 'mm', value: val * 1000 },
    { label: 'ft', value: val * 3.28084 },
    { label: 'in', value: val * 39.3701 },
  ],
  pressure: (val) => [
    { label: 'Pa', value: val },
    { label: 'kPa', value: val / 1000 },
    { label: 'MPa', value: val / 1000000 },
    { label: 'psi', value: val * 0.000145038 },
  ],
  mass: (val) => [
    { label: 'kg', value: val },
    { label: 'g', value: val * 1000 },
    { label: 'ton', value: val / 1000 },
    { label: 'lb', value: val * 2.20462 },
  ],
  distributed_load: (val) => [
    { label: 'N/m', value: val },
    { label: 'kN/m', value: val / 1000 },
    { label: 'N/mm', value: val / 1000 },
    { label: 'lb/ft', value: val * 0.0685218 },
  ],
  density: (val) => [
    { label: 'kg/m³', value: val },
    { label: 'g/cm³', value: val / 1000 },
    { label: 'lb/ft³', value: val * 0.062428 },
  ],
  torque: (val) => [
    { label: 'N·m', value: val },
    { label: 'kN·m', value: val / 1000 },
    { label: 'lb·ft', value: val * 0.737562 },
  ],
  constant: (val) => [
    { label: 'SI Value', value: val }
  ]
};

const formatValue = (val) => {
  if (val === 0) return '0';
  const absVal = Math.abs(val);
  if (absVal < 0.001 || absVal > 1000000) {
    return val.toExponential(3);
  }
  return val.toLocaleString(undefined, { 
    maximumFractionDigits: 3,
    minimumFractionDigits: 0
  });
};

export default function UnitLens({ units }) {
  if (!units || units.length === 0) return null;

  return (
    <div className="bg-[#151515] border border-white/10 rounded-xl overflow-hidden shadow-2xl">
      <div className="bg-white/5 px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2">
          <Repeat className="w-3 h-3 text-blue-400" /> Unit Analytics Engine
        </h4>
        <div className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-[8px] font-bold rounded uppercase">
          Auto-Conversion
        </div>
      </div>
      <div className="p-4 space-y-4">
        {units.map((u, i) => {
          const type = u.type?.toLowerCase() || 'unknown';
          const converter = CONVERSIONS[type];
          const options = converter ? converter(u.si_val) : [];

          return (
            <div key={i} className="space-y-2 border-b border-white/5 pb-4 last:border-0 last:pb-0">
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <span className="text-[10px] font-mono text-white/40 uppercase tracking-widest">
                    Extracted: <span className="text-white font-bold">{u.param || 'Value'}: {u.val}{u.unit}</span>
                  </span>
                  {u.warning && (
                    <div className="flex items-center gap-1 mt-1 text-amber-500">
                      <AlertTriangle className="w-3 h-3" />
                      <span className="text-[9px] font-bold uppercase tracking-tight">{u.warning}</span>
                    </div>
                  )}
                </div>
                <span className="text-[9px] font-black uppercase text-blue-400/60 tracking-tighter bg-blue-400/5 px-1.5 py-0.5 rounded">{type}</span>
              </div>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {options.map((opt, j) => (
                  <div key={j} className="bg-black/40 p-2 rounded border border-white/5 hover:border-blue-500/30 transition-colors group">
                    <div className="text-[8px] font-mono text-white/30 uppercase mb-1">{opt.label}</div>
                    <div className="text-[11px] font-bold truncate group-hover:text-blue-400 transition-colors">
                      {formatValue(opt.value)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
