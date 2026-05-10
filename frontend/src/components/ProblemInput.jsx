import React from 'react';
import { motion } from 'motion/react';
import { Zap, Camera, X } from 'lucide-react';

const ProblemInput = ({ 
  inputMode, 
  setInputMode, 
  inputText, 
  setInputText, 
  imagePreview, 
  setImagePreview, 
  handleCompute, 
  stopComputation,
  isProcessing, 
  online,
  fileInputRef,
  handleImageUpload
}) => {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-xl mx-auto py-20 space-y-12"
    >
      <div className="text-center space-y-4">
        <div className="inline-block p-1 px-3 bg-white/5 border border-white/10 rounded-full text-[10px] font-bold tracking-[0.2em] uppercase">
          Workspace Ready
        </div>
        <h2 className="text-4xl md:text-6xl font-black leading-none tracking-tighter">
          ENTER YOUR<br/><span className="text-transparent bg-clip-text bg-gradient-to-r from-white to-white/40">PROBLEM.</span>
        </h2>
        <p className="text-xs opacity-50 font-mono leading-relaxed uppercase">
          deterministic engine for structural analysis, mechanics, and advanced mathematics.
        </p>
      </div>

      <div className="bg-[#111] border border-white/10 rounded-xl p-2 space-y-2 shadow-2xl relative">
        <div className={`flex gap-1 p-1 bg-black/50 rounded-lg ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}>
          <button 
            onClick={() => setInputMode('text')}
            disabled={isProcessing}
            className={`flex-1 py-3 text-[10px] font-black uppercase tracking-widest rounded-md transition-all ${inputMode === 'text' ? 'bg-white text-black' : 'hover:bg-white/5'}`}
          >
            TEXT INPUT
          </button>
          <button 
            onClick={() => setInputMode('image')}
            disabled={isProcessing}
            className={`flex-1 py-3 text-[10px] font-black uppercase tracking-widest rounded-md transition-all ${inputMode === 'image' ? 'bg-white text-black' : 'hover:bg-white/5'}`}
          >
            IMAGE VISION
          </button>
        </div>

        {inputMode === 'text' ? (
          <textarea
            placeholder="Describe your problem (e.g., Cantilever beam length 5m with 10kN point load at center...)"
            className="w-full bg-transparent p-6 min-h-[160px] outline-none font-mono text-sm resize-none focus:placeholder-white/20 transition-all disabled:opacity-30"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isProcessing}
            id="input-text"
          />
        ) : (
          <div 
            onClick={() => !isProcessing && fileInputRef.current?.click()}
            className={`w-full min-h-[160px] border-2 border-dashed border-white/5 hover:border-white/20 rounded-lg flex flex-col items-center justify-center transition-all gap-4 py-8 group ${isProcessing ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
            id="input-image"
          >
            {imagePreview ? (
              <div className="relative">
                <img src={`data:image/jpeg;base64,${imagePreview}`} className="max-h-32 rounded border border-white/20" alt="Preview" />
                <button 
                  className="absolute -top-2 -right-2 bg-red-500 rounded-full p-1"
                  onClick={(e) => { e.stopPropagation(); setImagePreview(null); }}
                  disabled={isProcessing}
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ) : (
              <>
                <div className="p-4 bg-white/5 rounded-full group-hover:scale-110 transition-transform">
                  <Camera className="w-6 h-6 text-white/50" />
                </div>
                <span className="text-[10px] font-black uppercase tracking-[0.2em] opacity-40">Drop Image or Click to Capture</span>
              </>
            )}
            <input type="file" hidden ref={fileInputRef} accept="image/*" onChange={handleImageUpload} />
          </div>
        )}

        <button 
          onClick={isProcessing ? stopComputation : handleCompute}
          disabled={(!isProcessing && !online)}
          className={`w-full py-6 font-black uppercase text-xs tracking-[0.3em] flex items-center justify-center gap-3 active:scale-[0.98] transition-all disabled:opacity-50 disabled:active:scale-100 ${isProcessing ? 'bg-red-500 text-white hover:bg-red-600' : 'bg-white text-black'}`}
          id="compute-btn"
        >
          {isProcessing ? (
            <>STOP ENGINE <X className="w-4 h-4" /></>
          ) : (
            <>RUN ENGINE <Zap className="w-4 h-4" /></>
          )}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {[
          { label: "Mechanics", topics: "SFD, BMD, STRESS" },
          { label: "Mathematics", topics: "CALC, ALGEBRA, ODEs" },
          { label: "Circuits", topics: "OHM, KCL, KVL" },
          { label: "Fluid", topics: "BERNOULLI, REYNOLDS" }
        ].map((item, i) => (
          <div key={i} className="p-4 bg-white/5 border border-white/5 rounded-lg">
            <div className="text-[10px] font-black uppercase tracking-widest mb-1">{item.label}</div>
            <div className="text-[9px] font-mono opacity-30">{item.topics}</div>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

export default ProblemInput;
