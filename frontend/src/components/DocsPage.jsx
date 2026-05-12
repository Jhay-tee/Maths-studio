import React from 'react';
import { X } from 'lucide-react';

export default function DocsPage({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-[#111111] p-6 shadow-2xl">
        <div className="flex items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-black uppercase tracking-widest">Studio Technical Notes</h2>
            <p className="mt-1 text-xs text-white/40 font-mono">Kernel v2.4.0 • Engineering Standards compliant</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-white/10 p-2 text-white/70 hover:bg-white/5 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-6 overflow-y-auto max-h-[70vh] pr-2">
            <div>
              <h2 className="text-md font-bold text-white mb-3 flex items-center gap-2">
                <Activity className="w-5 h-5 text-orange-400" /> Uncertainty Propagation
              </h2>
              <div className="bg-white/5 border border-white/5 rounded-2xl p-5 space-y-4">
                 <p className="text-sm opacity-60 leading-relaxed">
                   The kernel uses first-order propagation (GUM standard) to calculate result tolerances.
                 </p>
                 <div className="space-y-4">
                   <div className="p-3 bg-black/40 rounded-xl border border-white/5">
                     <div className="text-[9px] font-black uppercase text-orange-400 mb-1">Example Query</div>
                     <code className="text-xs text-white/90">"Projectile motion: v0=20 +/- 0.5 m/s, angle=45, height=10m"</code>
                   </div>
                   <div className="text-xs text-white/70 leading-relaxed">
                     <strong>Format:</strong> Use <code className="text-orange-400">nominal +/- tolerance</code> or <code className="text-orange-400">value with X% error</code>.
                     The system automatically extracts these and propagates them through the governing equations.
                   </div>
                 </div>
              </div>
            </div>

            <div>
              <h2 className="text-md font-bold text-white mb-3">Complex Analysis</h2>
              <ul className="space-y-2 text-xs text-white/50">
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 mt-1">•</span>
                  <span><strong>3D Function Plots:</strong> Enter multivariable expressions like <code className="text-blue-400">z = x^2 - y^2</code> to generate topographic 3D surfaces.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 mt-1">•</span>
                  <span><strong>Structural FEM:</strong> Analyze 2D trusses and beams. Get shear, moment, and deflection curves.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-400 mt-1">•</span>
                  <span><strong>Control Systems:</strong> Plot Bode diagrams for frequency response analysis (Gain/Phase).</span>
                </li>
              </ul>
            </div>
            
            <div className="pt-4 border-t border-white/5 italic text-[10px] text-white/20 text-center">
              Professional validation required for actual fabrication or critical structural designs.
            </div>
        </div>
      </div>
    </div>
  );
}
