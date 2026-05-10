import { useCallback, useRef } from 'react';

export default function useLongPress(onLongPress, onClick, { delay = 500 } = {}) {
  const timeout = useRef();
  const target = useRef();

  const start = useCallback((event) => {
    if (event.target) target.current = event.target;
    timeout.current = setTimeout(() => {
      onLongPress(event);
      target.current = null;
    }, delay);
  }, [onLongPress, delay]);

  const clear = useCallback((event, shouldTriggerClick = true) => {
    if (timeout.current) clearTimeout(timeout.current);
    
    // Only trigger click if we haven't already triggered onLongPress
    if (shouldTriggerClick && target.current) {
      onClick?.(event);
    }
    
    target.current = null;
  }, [onClick]);

  return {
    onMouseDown: e => start(e),
    onTouchStart: e => start(e),
    onMouseUp: e => clear(e),
    onMouseLeave: e => clear(e, false),
    onTouchEnd: e => clear(e),
  };
}
