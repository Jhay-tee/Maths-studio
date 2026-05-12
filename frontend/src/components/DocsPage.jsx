import React from 'react';
import { X } from 'lucide-react';

export default function DocsPage({ onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-[#111111] p-6 shadow-2xl">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-black uppercase tracking-widest">Studio Notes</h2>
            <p className="mt-2 text-sm text-white/60">
              Documentation is not wired in yet. The main compute experience remains available.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-full border border-white/10 p-2 text-white/70 hover:bg-white/5 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
