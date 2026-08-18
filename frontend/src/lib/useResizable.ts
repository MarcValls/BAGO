// src/lib/useResizable.ts
// Hook para paneles redimensionables. Persiste tamaños en localStorage.
// Soporta layout horizontal (splitters verticales) y vertical
// (splitters horizontales).

import { useCallback, useEffect, useRef, useState } from 'react';

interface UseResizableOptions {
  /** Identificador único para persistir en localStorage. */
  id: string;
  /** Nombres de los paneles en orden. */
  panels: string[];
  /** Tamaños iniciales (en porcentaje) si no hay valor guardado. */
  defaultSizes: number[];
  /** Tamaños mínimos (en píxeles) por panel. */
  minSizes: number[];
  /** 'horizontal' = splitters verticales, 'vertical' = horizontales. */
  direction?: 'horizontal' | 'vertical';
  /** Storage backend. Por defecto localStorage. */
  storage?: Storage;
}

interface UseResizableState {
  /** Tamaños actuales en porcentaje. */
  sizes: number[];
  /** Ref que se aplica al contenedor padre. */
  containerRef: React.RefObject<HTMLDivElement>;
  /** Inicia un resize. Llamar en onMouseDown del handle. */
  startResize: (index: number) => void;
  /** Estilo flex para un panel. */
  getPanelStyle: (panelName: string) => React.CSSProperties;
  /** Resetea a los tamaños por defecto. */
  reset: () => void;
  /** Establece un panel a un tamaño específico. */
  setPanelSize: (panelName: string, size: number) => void;
}

export function useResizable(options: UseResizableOptions): UseResizableState {
  const direction = options.direction || 'horizontal';
  const storage = options.storage || (typeof window !== 'undefined' ? window.localStorage : null);
  const storageKey = `bago:layout:${options.id}`;
  const containerRef = useRef<HTMLDivElement | null>(null);

  const loadInitial = (): number[] => {
    if (!storage) return [...options.defaultSizes];
    try {
      const raw = storage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as number[];
        if (Array.isArray(parsed) && parsed.length === options.panels.length) {
          return parsed;
        }
      }
    } catch {
      // Ignorar errores de parseo.
    }
    return [...options.defaultSizes];
  };

  const [sizes, setSizes] = useState<number[]>(loadInitial);

  useEffect(() => {
    if (!storage) return;
    try {
      storage.setItem(storageKey, JSON.stringify(sizes));
    } catch {
      // Ignorar errores de quota.
    }
  }, [sizes, storage, storageKey]);

  const startResize = useCallback((handleIndex: number) => {
    const handleMouseMove = (event: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const total = direction === 'horizontal' ? rect.width : rect.height;
      const cursor = direction === 'horizontal' ? (event.clientX - rect.left) : (event.clientY - rect.top);
      const newSizes = [...sizes];
      let accumulated = 0;
      for (let i = 0; i < handleIndex; i++) {
        accumulated += (sizes[i] / 100) * total;
      }
      const leftPanelSize = ((cursor - accumulated + (sizes[handleIndex] / 100) * total) / total) * 100;
      newSizes[handleIndex] = Math.max(
        (options.minSizes[handleIndex] / total) * 100,
        Math.min(100 - (options.minSizes[handleIndex + 1] / total) * 100, leftPanelSize)
      );
      if (handleIndex + 1 < newSizes.length) {
        const totalUsed = newSizes.slice(0, handleIndex + 1).reduce((a, b) => a + b, 0);
        const remaining = 100 - totalUsed;
        newSizes[handleIndex + 1] = Math.max(
          (options.minSizes[handleIndex + 1] / total) * 100,
          Math.min(remaining, newSizes[handleIndex + 1] + (sizes[handleIndex] - newSizes[handleIndex]))
        );
      }
      setSizes(newSizes);
    };
    const handleMouseUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
    document.body.style.cursor = direction === 'horizontal' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  }, [sizes, options.minSizes, direction]);

  const getPanelStyle = useCallback((panelName: string): React.CSSProperties => {
    const index = options.panels.indexOf(panelName);
    if (index < 0) return {};
    const size = sizes[index] || 0;
    if (direction === 'horizontal') {
      return { flex: `0 0 ${size}%`, minWidth: 0 };
    }
    return { flex: `0 0 ${size}%`, minHeight: 0, height: `${size}%` };
  }, [sizes, options.panels, direction]);

  const reset = useCallback(() => {
    setSizes([...options.defaultSizes]);
  }, [options.defaultSizes]);

  const setPanelSize = useCallback((panelName: string, size: number) => {
    const index = options.panels.indexOf(panelName);
    if (index < 0) return;
    setSizes((current) => {
      const next = [...current];
      next[index] = size;
      return next;
    });
  }, [options.panels]);

  return { sizes, containerRef, startResize, getPanelStyle, reset, setPanelSize };
}
