import React from 'react';
import { Plus, Send, X, Image as ImageIcon, Square } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function ChatInput({ 
  inputText, 
  setInputText, 
  imagePreview, 
  setImagePreview, 
  dataFile,
  setDataFile,
  plotConfig,
  setPlotConfig,
  handleCompute, 
  isProcessing, 
  fileInputRef,
  onStop
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCompute();
    }
  };

  const onFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      const isImage = file.type.startsWith('image/');
      
      reader.onloadend = () => {
        const base64 = reader.result.split(',')[1];
        if (isImage) {
          setImagePreview(base64);
          setDataFile(null);
        } else {
          setDataFile({
            name: file.name,
            type: file.type,
            base64: base64
          });
          setImagePreview(null);
        }
      };
      
      if (isImage) {
        reader.readAsDataURL(file);
      } else {
        reader.readAsDataURL(file); 
      }
    }
  };

  return (
    <div className="w-full transition-all duration-300">
      <div className="relative bg-[#0b0b0b]/80 border border-white/10 rounded-[28px] shadow-[0_30px_100px_rgba(0,0,0,0.8)] p-2.5 flex flex-col transition-all focus-within:border-white/20 backdrop-blur-3xl">
        
        <AnimatePresence>
          {(imagePreview || dataFile) && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-4 pt-4 pb-2 flex flex-col gap-4 border-b border-white/5 mb-2"
            >
              <div className="flex items-center justify-between">
                <div className="relative inline-block">
                  {imagePreview ? (
                    <img 
                      src={`data:image/jpeg;base64,${imagePreview}`} 
                      className="w-20 h-20 object-cover rounded-xl border border-white/10" 
                      alt="Preview" 
                    />
                  ) : (
                    <div className="w-20 h-20 bg-blue-500/10 rounded-xl border border-blue-500/20 flex flex-col items-center justify-center p-2 text-center overflow-hidden">
                      <ImageIcon className="w-6 h-6 text-blue-400 mb-1" />
                      <span className="text-[8px] font-mono text-blue-400 truncate w-full px-2">{dataFile?.name}</span>
                    </div>
                  )}
                  <button 
                    onClick={() => { setImagePreview(null); setDataFile(null); }}
                    className="absolute -top-2 -right-2 bg-white text-black p-1 rounded-full shadow-lg hover:scale-110 transition-transform"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>

                {dataFile && (
                  <div className="flex-1 ml-6 grid grid-cols-2 gap-4">
                    <div className="space-y-1.5 transition-all">
                      <label className="text-[9px] font-black uppercase tracking-widest text-white/40">Plot Mode</label>
                      <div className="flex bg-white/5 p-1 rounded-lg">
                        {['line', 'scatter', 'bar'].map(t => (
                          <button
                            key={t}
                            onClick={() => setPlotConfig({...plotConfig, type: t})}
                            className={`flex-1 px-2 py-1.5 rounded-md text-[9px] font-black uppercase transition-all ${plotConfig.type === t ? 'bg-white text-black' : 'text-white/40 hover:text-white'}`}
                          >
                            {t}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[9px] font-black uppercase tracking-widest text-white/40">Y-Axis Label</label>
                      <input 
                        type="text" 
                        placeholder="Stress (σ)..."
                        value={plotConfig.ylabel}
                        onChange={(e) => setPlotConfig({...plotConfig, ylabel: e.target.value})}
                        className="w-full bg-white/5 border-0 focus:ring-1 focus:ring-white/20 rounded-lg p-2 text-[10px] text-white placeholder:text-white/10"
                      />
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-2 px-1">
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="p-3.5 hover:bg-white/5 text-white/30 hover:text-white rounded-full transition-all"
          >
            <Plus className="w-5 h-5" />
          </button>
          
          <input 
            type="file" 
            ref={fileInputRef} 
            className="hidden" 
            accept="image/*,.csv,.xlsx,.xls" 
            onChange={onFileChange}
          />

          <textarea
            className="flex-1 bg-transparent border-0 focus:ring-0 focus:outline-none text-[15px] font-medium p-4 max-h-[200px] min-h-[56px] resize-none placeholder:text-white/20 select-none shadow-none leading-relaxed"
            placeholder="Compute your next engineering challenge..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />

          {isProcessing ? (
            <button
              onClick={onStop}
              className="p-4 rounded-full transition-all bg-white text-black hover:bg-white/90 active:scale-95 shadow-2xl"
            >
              <Square className="w-5 h-5 fill-current" />
            </button>
          ) : (
            <button 
              onClick={handleCompute}
              disabled={!inputText.trim() && !imagePreview && !dataFile}
              className={`p-4 rounded-full transition-all ${
                (!inputText.trim() && !imagePreview && !dataFile)
                ? 'text-white/10 cursor-not-allowed'
                : 'bg-white text-black hover:scale-105 active:scale-95 shadow-2xl'
              }`}
            >
              <Send className="w-5 h-5 fill-current" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
