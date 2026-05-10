import React, { useRef } from 'react';
import { Plus, Send, X, Image as ImageIcon, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function ChatInput({ 
  inputText, 
  setInputText, 
  imagePreview, 
  setImagePreview, 
  handleCompute, 
  isProcessing, 
  fileInputRef 
}) {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCompute();
    }
  };

  const onImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result.split(',')[1]);
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="max-w-4xl mx-auto w-full transition-all duration-300">
      <div className="relative bg-[#1a1a1a] border border-white/10 rounded-[24px] shadow-2xl p-2 flex flex-col transition-all focus-within:border-white/20 focus-within:shadow-[0_0_30px_rgba(255,255,255,0.05)]">
        
        <AnimatePresence>
          {imagePreview && (
            <motion.div 
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-4 pt-4 pb-2 relative"
            >
              <div className="relative inline-block">
                <img 
                  src={`data:image/jpeg;base64,${imagePreview}`} 
                  className="w-20 h-20 object-cover rounded-xl border border-white/10" 
                  alt="Preview" 
                />
                <button 
                  onClick={() => setImagePreview(null)}
                  className="absolute -top-2 -right-2 bg-white text-black p-1 rounded-full shadow-lg hover:scale-110 transition-transform"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-end gap-2 px-2">
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="p-3 hover:bg-white/5 text-white/40 hover:text-white rounded-full transition-all mb-1"
          >
            <Plus className="w-6 h-6" />
          </button>
          
          <input 
            type="file" 
            ref={fileInputRef} 
            className="hidden" 
            accept="image/*" 
            onChange={onImageChange}
          />

          <textarea
            className="flex-1 bg-transparent border-0 focus:ring-0 text-sm font-medium p-4 max-h-[150px] min-h-[56px] resize-none placeholder:text-white/20"
            placeholder="Describe your engineering problem..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />

          <button 
            onClick={handleCompute}
            disabled={isProcessing || (!inputText.trim() && !imagePreview)}
            className={`p-3 rounded-full transition-all mb-1 ${
              isProcessing || (!inputText.trim() && !imagePreview)
              ? 'bg-white/5 text-white/10 cursor-not-allowed'
              : 'bg-white text-black hover:scale-105 active:scale-95 shadow-xl'
            }`}
          >
            {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
          </button>
        </div>
      </div>
      
      <div className="mt-4 flex flex-wrap justify-center gap-4 px-4 overflow-x-auto no-scrollbar pb-2">
        {['Structural', 'Fluids', 'Thermo', 'Mechanics', 'Calculus'].map(topic => (
          <button 
            key={topic}
            onClick={() => setInputText(prev => prev + (prev ? ' ' : '') + topic + ' ')}
            className="text-[9px] font-black uppercase tracking-widest text-white/30 hover:text-white transition-colors border border-white/5 px-3 py-1 rounded-full hover:bg-white/5"
          >
            {topic}
          </button>
        ))}
      </div>
    </div>
  );
}
