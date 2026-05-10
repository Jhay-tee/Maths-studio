import React, { useRef, useEffect } from 'react';

const StudioCanvas = ({ type, data, width = 600, height = 300 }) => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data) return;
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
      
      // Select color based on type
      if (type.includes('shear')) ctx.strokeStyle = '#4ade80'; // Green
      else if (type.includes('bending') || type.includes('moment')) ctx.strokeStyle = '#60a5fa'; // Blue
      else if (type.includes('axial') || type.includes('force')) ctx.strokeStyle = '#fb923c'; // Orange
      else if (type.includes('stress')) ctx.strokeStyle = '#f87171'; // Red
      else if (type.includes('pressure')) ctx.strokeStyle = '#a78bfa'; // Purple
      else if (type.includes('pv_diagram')) ctx.strokeStyle = '#f472b6'; // Pink
      else ctx.strokeStyle = '#ffffff';

      data.forEach((point, i) => {
        const px = padding + point.x * scaleX;
        const py = centerY - point.y * scaleY;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
        
        // Fill area for better visibility
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

        // Label points with units
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

      // Title
      ctx.font = '12px monospace';
      ctx.fillText(type.replace(/_/g, ' ').toUpperCase(), padding, padding - 10);
    }
  }, [data, type, width, height]);

  return (
    <div className="bg-[#0b0b0b] p-4 border border-white/10 rounded-lg overflow-hidden my-4 shadow-2xl">
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
