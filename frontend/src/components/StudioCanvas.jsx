import React, { useRef, useEffect } from 'react';
import { Download, Table, Image as ImageIcon, FileText, Activity } from 'lucide-react';
import DataTable from './DataTable';

const StudioCanvas = ({ type, data, width = 600, height = 300 }) => {
  const canvasRef = useRef(null);

  const downloadFile = (fileData, filename, fileType) => {
    const blob = new Blob([fileData], { type: fileType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const downloadDataUrl = (dataUrl, filename) => {
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  useEffect(() => {
    if (type === 'plot' || !canvasRef.current || !data || !Array.isArray(data)) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // Set styles
    ctx.fillStyle = '#0b0b0b';
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.font = '10px monospace';
    ctx.fillStyle = '#ffffff';

    const padding = 40;
    const chartW = width - 2 * padding;
    const chartH = height - 2 * padding;

    // Draw Axes
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, height - padding);
    ctx.lineTo(width - padding, height - padding);
    ctx.stroke();

    if (data.length > 0) {
      const maxX = Math.max(...data.map(p => p.x));
      const maxY = Math.max(...data.map(p => Math.abs(p.y)));
      
      const scaleX = chartW / (maxX || 1);
      const scaleY = chartH / (2 * (maxY || 1));
      const centerY = padding + chartH / 2;

      // Draw Zero Line
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(padding, centerY);
      ctx.lineTo(width - padding, centerY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw Data
      ctx.beginPath();
      
      if (type.includes('shear')) ctx.strokeStyle = '#4ade80';
      else if (type.includes('bending') || type.includes('moment')) ctx.strokeStyle = '#60a5fa';
      else if (type.includes('axial') || type.includes('force')) ctx.strokeStyle = '#fb923c';
      else if (type.includes('stress')) ctx.strokeStyle = '#f87171';
      else if (type.includes('pressure')) ctx.strokeStyle = '#a78bfa';
      else if (type.includes('pv_diagram')) ctx.strokeStyle = '#f472b6';
      else ctx.strokeStyle = '#ffffff';

      data.forEach((point, i) => {
        const px = padding + point.x * scaleX;
        const py = centerY - point.y * scaleY;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
        
        if (i > 0) {
          const prevX = padding + data[i-1].x * scaleX;
          const prevY = centerY - data[i-1].y * scaleY;
          ctx.globalAlpha = 0.1;
          ctx.beginPath();
          ctx.moveTo(prevX, centerY);
          ctx.lineTo(prevX, prevY);
          ctx.lineTo(px, py);
          ctx.lineTo(px, centerY);
          ctx.closePath();
          ctx.fillStyle = ctx.strokeStyle;
          ctx.fill();
          ctx.globalAlpha = 1.0;
          ctx.beginPath();
          ctx.moveTo(prevX, prevY);
          ctx.lineTo(px, py);
        }

        if (i % 20 === 0 || i === data.length - 1) {
          let unit = '';
          if (type.includes('moment')) unit = ' Nm';
          else if (type.includes('force')) unit = ' N';
          else if (type.includes('displacement')) unit = ' mm';
          else if (type.includes('stress')) unit = ' MPa';
          
          ctx.fillStyle = '#ffffff';
          ctx.fillText(`${point.y.toFixed(1)}${unit}`, px, py - 5);
          ctx.fillText(`${point.x.toFixed(1)}m`, px, height - padding + 15);
        }
      });
      ctx.stroke();

      ctx.font = '12px monospace';
      ctx.fillText(type.replace(/_/g, ' ').toUpperCase(), padding, padding - 10);
    }
  }, [data, type, width, height]);

  if (type === 'plot') {
    return (
      <div className="space-y-4">
        <div className="bg-[#1a1a1a] border border-white/5 rounded-[24px] overflow-hidden shadow-2xl group relative">
          <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
            <button 
              onClick={() => downloadDataUrl(data.image, 'plot.png')}
              className="p-2 bg-black/60 rounded-xl hover:bg-white hover:text-black transition-all"
              title="Download PNG"
            >
              <ImageIcon className="w-4 h-4" />
            </button>
            <button 
              onClick={() => downloadDataUrl(data.svg, 'plot.svg')}
              className="p-2 bg-black/60 rounded-xl hover:bg-white hover:text-black transition-all"
              title="Download SVG"
            >
              <Download className="w-4 h-4" />
            </button>
          </div>
          <img src={data.image} alt={data.caption} className="w-full h-auto" />
          
          <div className="p-4 bg-white/5 border-t border-white/5 flex items-center justify-between">
            <div className="flex items-center gap-2 text-[10px] uppercase font-bold tracking-widest text-white/30">
              <Activity className="w-3 h-3" /> Technical Analysis
            </div>
            {data.csv && (
              <button 
                onClick={() => downloadFile(data.csv, 'data.csv', 'text/csv')}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white hover:text-black transition-all text-[10px] font-bold uppercase"
              >
                <FileText className="w-3 h-3" /> Export CSV
              </button>
            )}
          </div>
        </div>

        {data.table_json && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-widest text-white/20">
              <Table className="w-3.5 h-3.5" /> Interactive Result Table
            </div>
            <DataTable data={data.table_json} columns={data.columns} />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="bg-[#0b0b0b] p-4 border border-white/10 rounded-lg overflow-hidden my-4 shadow-2xl relative group">
      <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
        <button 
          onClick={() => {
            const canvas = canvasRef.current;
            const link = document.createElement('a');
            link.download = `${type}.png`;
            link.href = canvas.toDataURL();
            link.click();
          }}
          className="p-2 bg-white text-black rounded-lg hover:scale-105 transition-all"
        >
          <Download className="w-4 h-4" />
        </button>
      </div>
      <canvas 
        ref={canvasRef} 
        width={width} 
        height={height} 
        className="w-full h-auto"
        id={`canvas-${type}`}
      />
    </div>
  );
};

export default StudioCanvas;
