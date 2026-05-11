import { useCallback, useRef, useEffect } from 'react';

export default function useLongPress(onLongPress, onClick, { delay = 3000 } = {}) {
  const timeout = useRef();
  const target = useRef();
  const startPos = useRef({ x: 0, y: 0 });
  const isActive = useRef(false);

  const start = useCallback((event) => {
    const touch = event.touches ? event.touches[0] : event;
    startPos.current = { x: touch.clientX, y: touch.clientY };
    target.current = event.target;
    isActive.current = true;

    timeout.current = setTimeout(() => {
      if (isActive.current) {
        onLongPress(event);
      }
      target.current = null;
    }, delay);
  }, [onLongPress, delay]);

  const clear = useCallback((event, shouldTriggerClick = true) => {
    const hasTimedOut = !timeout.current;

    if (timeout.current) {
      clearTimeout(timeout.current);
      timeout.current = null;
    }

    if (shouldTriggerClick && target.current && !hasTimedOut) {
      onClick?.(event);
    }

    target.current = null;
    isActive.current = false;
  }, [onClick]);

  const move = useCallback((event) => {
    if (!timeout.current || !isActive.current) return;

    const touch = event.touches ? event.touches[0] : event;
    const moveX = Math.abs(touch.clientX - startPos.current.x);
    const moveY = Math.abs(touch.clientY - startPos.current.y);

    if (moveX > 10 || moveY > 10) {
      clearTimeout(timeout.current);
      timeout.current = null;
      target.current = null;
      isActive.current = false;
    }
  }, []);

  // Handle escape key to deactivate
  useEffect(() => {
    const handleEscape = () => {
      if (timeout.current) {
        clearTimeout(timeout.current);
        timeout.current = null;
      }
      target.current = null;
      isActive.current = false;
    };

    const handleDocumentClick = (e) => {
      if (isActive.current && target.current && !target.current.contains(e.target)) {
        handleEscape();
      }
    };

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') handleEscape();
    });
    document.addEventListener('click', handleDocumentClick, true);

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('click', handleDocumentClick, true);
    };
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
