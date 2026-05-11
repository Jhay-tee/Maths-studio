import { useCallback, useRef } from 'react';

export default function useLongPress(onLongPress, onClick, { delay = 3000 } = {}) {
  const timeout = useRef();
  const target = useRef();
  const startPos = useRef({ x: 0, y: 0 });

  const start = useCallback((event) => {
    // Record starting position to detect movement
    const touch = event.touches ? event.touches[0] : event;
    startPos.current = { x: touch.clientX, y: touch.clientY };

    if (event.target) target.current = event.target;
    timeout.current = setTimeout(() => {
      onLongPress(event);
      target.current = null;
    }, delay);
  }, [onLongPress, delay]);

  const clear = useCallback((event, shouldTriggerClick = true) => {
    if (timeout.current) {
      clearTimeout(timeout.current);
      timeout.current = null;
    }
    
    // Only trigger click if we haven't already triggered onLongPress
    if (shouldTriggerClick && target.current) {
      onClick?.(event);
    }
    
    target.current = null;
  }, [onClick]);

  const move = useCallback((event) => {
    if (!timeout.current) return;

    const touch = event.touches ? event.touches[0] : event;
    const moveX = Math.abs(touch.clientX - startPos.current.x);
    const moveY = Math.abs(touch.clientY - startPos.current.y);

    // If moved more than 10px, cancel the long press
    if (moveX > 10 || moveY > 10) {
      if (timeout.current) {
        clearTimeout(timeout.current);
        timeout.current = null;
      }
      target.current = null;
    }
  }, []);

  return {
    onMouseDown: e => start(e),
    onTouchStart: e => start(e),
    onMouseMove: e => move(e),
    onTouchMove: e => move(e),
    onMouseUp: e => clear(e),
    onMouseLeave: e => clear(e, false),
    onTouchEnd: e => clear(e),
  };
}
