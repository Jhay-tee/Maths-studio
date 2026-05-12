import React, { useRef, useEffect } from 'react';
import { Download, Table, Image as ImageIcon, FileText, Activity, Maximize2, Minimize2, RefreshCw } from 'lucide-react';
import { TransformWrapper, TransformComponent } from 'react-zoom-pan-pinch';
import DataTable from './DataTable';

const StudioCanvas = ({ type, data, width = 600, height = 300 }) => {
  const canvasRef = useRef(null);

  const renderDiagram = (diagramData) => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    // Background
    ctx.fillStyle = '#0b0b0b';
    ctx.fillRect(0, 0, w, h);

    if (type === 'force_diagram') {
      renderForceDiagram(ctx, w, h, diagramData);
    } else if (type === 'vibration_response') {
      renderVibrationDiagram(ctx, w, h, diagramData);
    } else if (type === 'trajectory') {
      renderTrajectoryDiagram(ctx, w, h, diagramData);
    } else if (type === 'circuit_ohms') {
      renderCircuitDiagram(ctx, w, h, diagramData);
    } else if (type === 'resistor_network') {
      renderNetworkDiagram(ctx, w, h, diagramData);
    } else if (type === 'beam_analysis') {
      renderBeamDiagrams(ctx, w, h, diagramData);
    } else if (type === 'matrix') {
      renderMatrixDiagram(ctx, w, h, diagramData);
    }
  };

  const renderMatrixDiagram = (ctx, w, h, data) => {
    const values = data.values || [];
    const rows = data.rows || values.length || 0;
    const cols = data.cols || values[0]?.length || 0;
    if (!rows || !cols) return;

    const cellWidth = Math.min(90, (w - 120) / cols);
    const cellHeight = Math.min(60, (h - 120) / rows);
    const gridWidth = cols * cellWidth;
    const gridHeight = rows * cellHeight;
    const startX = (w - gridWidth) / 2;
    const startY = (h - gridHeight) / 2;

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.strokeRect(startX - 14, startY - 14, gridWidth + 28, gridHeight + 28);

    ctx.font = 'bold 14px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    values.forEach((row, rowIndex) => {
      row.forEach((value, colIndex) => {
        const x = startX + colIndex * cellWidth;
        const y = startY + rowIndex * cellHeight;
        ctx.fillStyle = 'rgba(255,255,255,0.04)';
        ctx.fillRect(x, y, cellWidth - 6, cellHeight - 6);
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.strokeRect(x, y, cellWidth - 6, cellHeight - 6);
        ctx.fillStyle = '#f8fafc';
        ctx.fillText(String(value), x + (cellWidth - 6) / 2, y + (cellHeight - 6) / 2);
      });
    });

    ctx.fillStyle = '#60a5fa';
    ctx.font = 'bold 12px monospace';
    ctx.fillText(`${rows} x ${cols} Matrix`, w / 2, 26);
  };

  const renderForceDiagram = (ctx, w, h, data) => {
    const centerX = w / 2;
    const centerY = h / 2;
    const scale = Math.min(w, h) * 0.3;

    // Draw mass (box)
    ctx.fillStyle = '#4ade80';
    ctx.fillRect(centerX - 30, centerY - 20, 60, 40);
    ctx.fillStyle = '#0b0b0b';
    ctx.font = 'bold 12px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${data.mass.toFixed(1)}kg`, centerX, centerY + 5);

    // Draw force vector
    if (data.force !== 0) {
      const arrowLen = Math.min(Math.abs(data.force) / 10, scale);
      const startX = centerX + 40;
      const endX = startX + arrowLen * Math.sign(data.force);

      ctx.strokeStyle = data.force > 0 ? '#ef4444' : '#3b82f6';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(startX, centerY);
      ctx.lineTo(endX, centerY);
      ctx.stroke();

      // Arrow head
      const angle = data.force > 0 ? 0 : Math.PI;
      ctx.beginPath();
      ctx.moveTo(endX, centerY);
      ctx.lineTo(endX - 10 * Math.cos(angle - Math.PI / 6), centerY - 10 * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(endX - 10 * Math.cos(angle + Math.PI / 6), centerY - 10 * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();

      ctx.fillStyle = '#ffffff';
      ctx.fillText(`F = ${data.force.toFixed(1)} N`, w / 2, h - 40);
      ctx.fillText(`a = ${data.acceleration.toFixed(2)} m/s²`, w / 2, h - 20);
    }
  };

  const renderVibrationDiagram = (ctx, w, h, data) => {
    if (!data.t || !data.x) return;

    const padding = 40;
    const plotW = w - 2 * padding;
    const plotH = h - 2 * padding;

    const minT = Math.min(...data.t);
    const maxT = Math.max(...data.t);
    const minX = Math.min(...data.x);
    const maxX = Math.max(...data.x);

    const scaleX = plotW / (maxT - minT || 1);
    const scaleY = plotH / (maxX - minX || 1);

    // Draw axes
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding, padding);
    ctx.lineTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.stroke();

    // Draw waveform
    ctx.strokeStyle = '#60a5fa';
    ctx.lineWidth = 2;
    ctx.beginPath();
    data.t.forEach((t, i) => {
      const x = padding + (t - minT) * scaleX;
      const y = h - padding - (data.x[i] - minX) * scaleY;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#ffffff';
    ctx.font = '10px monospace';
    ctx.fillText('Time (s)', w - 20, h - 10);
    ctx.save();
    ctx.translate(10, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Displacement (m)', 0, 0);
    ctx.restore();
  };

  const renderTrajectoryDiagram = (ctx, w, h, data) => {
    if (!data.x || !data.y) return;

    const padding = 30;
    const plotW = w - 2 * padding;
    const plotH = h - 2 * padding;

    const maxX = Math.max(...data.x);
    const maxY = Math.max(...data.y);

    const scaleX = plotW / (maxX || 1);
    const scaleY = plotH / (maxY || 1);

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(padding, h - padding);
    ctx.lineTo(w - padding, h - padding);
    ctx.lineTo(w - padding, padding);
    ctx.stroke();

    // Trajectory path
    ctx.strokeStyle = '#fbbf24';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    data.x.forEach((x, i) => {
      const px = padding + x * scaleX;
      const py = h - padding - data.y[i] * scaleY;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#ffffff';
    ctx.font = '10px monospace';
    ctx.fillText('Range (m)', w - 30, h - 10);
    ctx.save();
    ctx.translate(10, h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Height (m)', 0, 0);
    ctx.restore();
  };

  const renderCircuitDiagram = (ctx, w, h, data) => {
    const centerX = w / 2;
    const centerY = h / 2;

    // Draw simple circuit representation
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.rect(centerX - 60, centerY - 40, 120, 80);
    ctx.stroke();

    ctx.fillStyle = '#60a5fa';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`V = ${data.voltage.toFixed(2)} V`, centerX, centerY - 15);
    ctx.fillText(`I = ${data.current.toFixed(4)} A`, centerX, centerY + 5);
    ctx.fillText(`R = ${data.resistance.toFixed(2)} Ω`, centerX, centerY + 25);
    ctx.fillStyle = '#4ade80';
    ctx.font = '10px monospace';
    ctx.fillText(`P = ${data.power.toFixed(2)} W`, centerX, centerY + 45);
  };

  const renderNetworkDiagram = (ctx, w, h, data) => {
    const centerY = h / 2;
    const startX = 50;
    const endX = w - 50;

    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 2;

    if (data.mode === 'series') {
      // Draw resistors in series
      const spacing = (endX - startX) / (data.resistors.length + 1);
      data.resistors.forEach((r, i) => {
        const x = startX + (i + 1) * spacing;
        ctx.fillStyle = '#fb923c';
        ctx.fillRect(x - 15, centerY - 10, 30, 20);
        ctx.fillStyle = '#0b0b0b';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${r.toFixed(0)}Ω`, x, centerY + 3);
      });
      // Connection lines
      ctx.beginPath();
      ctx.moveTo(startX, centerY);
      ctx.lineTo(endX, centerY);
      ctx.stroke();
    } else {
      // Parallel representation
      ctx.fillStyle = '#60a5fa';
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Parallel Network', w / 2, h / 2 - 20);
      ctx.fillStyle = '#ffffff';
      data.resistors.forEach((r, i) => {
        const y = h / 2 + (i - (data.resistors.length - 1) / 2) * 25;
        ctx.fillText(`${r.toFixed(0)}Ω`, w / 2, y);
      });
    }

    ctx.fillStyle = '#4ade80';
    ctx.font = 'bold 11px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`R_eq = ${data.equivalent.toFixed(2)}Ω`, w / 2, h - 20);
  };

  const renderBeamDiagrams = (ctx, w, h, data) => {
    if (!data.x || !data.shear || !data.moment) return;

    const padding = 30;
    const halfH = (h - padding * 3) / 2;

    // Shear diagram (top)
    drawBeamDiagram(ctx, padding, padding, w - 2 * padding, halfH, data.x, data.shear, '#4ade80', 'Shear (N)');

    // Moment diagram (bottom)
    drawBeamDiagram(ctx, padding, padding * 2 + halfH, w - 2 * padding, halfH, data.x, data.moment, '#60a5fa', 'Moment (Nm)');
  };

  const drawBeamDiagram = (ctx, x, y, w, h, xData, yData, color, label) => {
    const padding = 20;
    const plotW = w - 2 * padding;
    const plotH = h - 2 * padding;

    const minX = Math.min(...xData);
    const maxX = Math.max(...xData);
    const minY = Math.min(...yData);
    const maxY = Math.max(...yData);
    const rangeY = Math.max(Math.abs(minY), Math.abs(maxY)) || 1;

    const scaleX = plotW / (maxX - minX || 1);
    const scaleY = plotH / (2 * rangeY);
    const centerY = y + padding + plotH / 2;

    // Axes
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + padding, y + padding);
    ctx.lineTo(x + padding, y + h - padding);
    ctx.lineTo(x + w - padding, y + h - padding);
    ctx.stroke();

    // Zero line
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x + padding, centerY);
    ctx.lineTo(x + w - padding, centerY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Data curve
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    yData.forEach((val, i) => {
      const px = x + padding + (xData[i] - minX) * scaleX;
      const py = centerY - val * scaleY;
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // Label
    ctx.fillStyle = color;
    ctx.font = 'bold 10px monospace';
    ctx.fillText(label, x + w / 2, y + padding - 5);
  };

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
    if (type === 'plot' || !canvasRef.current || !data) return;

    // Handle object-based diagrams (not array-based)
    if (typeof data === 'object' && !Array.isArray(data)) {
      renderDiagram(data);
      return;
    }

    if (!Array.isArray(data)) return;
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
          <TransformWrapper
            initialScale={1}
            initialPositionX={0}
            initialPositionY={0}
            centerOnInit
          >
            {({ zoomIn, zoomOut, resetTransform }) => (
              <>
                <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                  <button 
                    onClick={() => zoomIn()}
                    className="p-2 bg-black/60 rounded-xl hover:bg-white hover:text-black transition-all"
                    title="Zoom In"
                  >
                    <Maximize2 className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => zoomOut()}
                    className="p-2 bg-black/60 rounded-xl hover:bg-white hover:text-black transition-all"
                    title="Zoom Out"
                  >
                    <Minimize2 className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => resetTransform()}
                    className="p-2 bg-black/60 rounded-xl hover:bg-white hover:text-black transition-all"
                    title="Reset"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
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
                <TransformComponent wrapperClass="!w-full !h-auto">
                  <img src={data.image} alt={data.caption} className="w-full h-auto cursor-grab active:cursor-grabbing" />
                </TransformComponent>
              </>
            )}
          </TransformWrapper>
          
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

  if (type === 'matrix') {
    return (
      <div className="space-y-3">
        <div className="bg-[#0b0b0b] p-4 border border-white/10 rounded-[24px] overflow-hidden shadow-2xl relative group">
          <canvas
            ref={canvasRef}
            width={width}
            height={height}
            className="w-full h-auto"
            id={`canvas-${type}`}
          />
        </div>
        {data?.caption && (
          <p className="text-xs text-white/50 leading-6">{data.caption}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="bg-[#0b0b0b] p-4 border border-white/10 rounded-[24px] overflow-hidden shadow-2xl relative group">
        <TransformWrapper
          initialScale={1}
          initialPositionX={0}
          initialPositionY={0}
          centerOnInit
        >
          {({ zoomIn, zoomOut, resetTransform }) => (
            <>
              <div className="absolute top-4 right-4 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                <button
                  onClick={() => zoomIn()}
                  className="p-1.5 bg-white text-black rounded-lg hover:scale-110 transition-all shadow-lg"
                  title="Zoom In"
                >
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => zoomOut()}
                  className="p-1.5 bg-white text-black rounded-lg hover:scale-110 transition-all shadow-lg"
                  title="Zoom Out"
                >
                  <Minimize2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => resetTransform()}
                  className="p-1.5 bg-white text-black rounded-lg hover:scale-110 transition-all shadow-lg"
                  title="Reset"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => {
                    const canvas = canvasRef.current;
                    const link = document.createElement('a');
                    link.download = `${type}.png`;
                    link.href = canvas.toDataURL();
                    link.click();
                  }}
                  className="p-1.5 bg-white text-black rounded-lg hover:scale-110 transition-all shadow-lg"
                  title="Download PNG"
                >
                  <Download className="w-3.5 h-3.5" />
                </button>
              </div>
              <TransformComponent wrapperClass="!w-full !h-auto">
                <canvas
                  ref={canvasRef}
                  width={width}
                  height={height}
                  className="w-full h-auto cursor-grab active:cursor-grabbing"
                  id={`canvas-${type}`}
                />
              </TransformComponent>
            </>
          )}
        </TransformWrapper>
      </div>

      {Array.isArray(data) && data.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-widest text-white/20">
            <Table className="w-3.5 h-3.5" /> Data Distribution (Interactive)
          </div>
          <DataTable data={data} columns={['x', 'y']} />
        </div>
      )}

      {typeof data === 'object' && !Array.isArray(data) && data.x && data.shear && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-1 text-[10px] font-black uppercase tracking-widest text-white/20">
            <Table className="w-3.5 h-3.5" /> Beam Analysis Data
          </div>
          <div className="grid grid-cols-2 gap-3 text-[10px]">
            <div className="bg-white/5 p-2 rounded text-white/60">
              <div className="font-mono">Max Shear: <span className="text-green-400">{data.max_shear?.toFixed(2)}</span> N</div>
            </div>
            <div className="bg-white/5 p-2 rounded text-white/60">
              <div className="font-mono">Max Moment: <span className="text-blue-400">{data.max_moment?.toFixed(2)}</span> Nm</div>
            </div>
            <div className="bg-white/5 p-2 rounded text-white/60">
              <div className="font-mono">Max Deflection: <span className="text-yellow-400">{(data.max_deflection * 1000)?.toFixed(2)}</span> mm</div>
            </div>
            <div className="bg-white/5 p-2 rounded text-white/60">
              <div className="font-mono">Type: <span className="text-purple-400 uppercase">{data.type}</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StudioCanvas;
