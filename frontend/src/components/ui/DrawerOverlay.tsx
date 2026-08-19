import { useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface DrawerOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  position?: 'left' | 'right' | 'bottom';
  width?: number | string;
  height?: number | string;
}

export function DrawerOverlay({
  isOpen,
  onClose,
  children,
  position = 'right',
  width = 360,
  height = 'auto',
}: DrawerOverlayProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const toggleFullscreen = useCallback(() => setIsFullscreen((v) => !v), []);

  if (!isOpen) return null;

  const isHorizontal = position === 'left' || position === 'right';

  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 100,
  };

  const backdropStyle: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    backdropFilter: 'blur(2px)',
  };

  const panelStyle: React.CSSProperties = isFullscreen
    ? {
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        backgroundColor: 'var(--surface)',
        boxShadow: 'var(--shadow)',
        overflow: 'auto',
        animation: 'slideIn 250ms ease-out',
      }
    : {
        position: 'absolute',
        top: position === 'bottom' ? 'auto' : 0,
        bottom: position === 'bottom' ? 0 : 'auto',
        left: position === 'right' ? 'auto' : 0,
        right: position === 'left' ? 'auto' : 0,
        width: isHorizontal ? (typeof width === 'number' ? `${width}px` : width) : '100%',
        height: !isHorizontal ? (typeof height === 'number' ? `${height}px` : height) : '100%',
        backgroundColor: 'var(--surface)',
        boxShadow: 'var(--shadow)',
        overflow: 'auto',
        animation: 'slideIn 250ms ease-out',
      };

  const toggleStyle: React.CSSProperties = {
    position: 'absolute',
    top: 10,
    left: 10,
    zIndex: 101,
    width: 30,
    height: 30,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 0,
    border: '1px solid var(--border)',
    borderRadius: 6,
    background: 'var(--surface)',
    color: 'var(--text-2)',
    cursor: 'pointer',
  };

  return (
    <div style={overlayStyle} role="complementary" aria-label="Panel lateral">
      <div style={backdropStyle} onClick={onClose} aria-hidden="true" />
      <div style={panelStyle}>
        <button
          type="button"
          style={toggleStyle}
          aria-label={isFullscreen ? 'Restaurar tamaño' : 'Mostrar a pantalla completa'}
          title={isFullscreen ? 'Restaurar' : 'Pantalla completa'}
          onClick={toggleFullscreen}
        >
          {isFullscreen ? '⛶' : '⛶'}
        </button>
        {children}
      </div>
      <style>{`
        @keyframes slideIn {
          from {
            transform: ${position === 'left' ? 'translateX(-100%)' : position === 'right' ? 'translateX(100%)' : 'translateY(100%)'};
          }
          to {
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
  );
}
