import { useState, useCallback, useEffect } from 'react';

export type DrawerId = 'capabilities' | 'system' | 'pipeline' | 'tools';

interface UsePanelManagerReturn {
  openDrawer: DrawerId | null;
  open: (drawer: DrawerId) => void;
  close: () => void;
  toggle: (drawer: DrawerId) => void;
  isOpen: (drawer: DrawerId) => boolean;
}

export function usePanelManager(): UsePanelManagerReturn {
  const [openDrawer, setOpenDrawer] = useState<DrawerId | null>(null);

  const open = useCallback((drawer: DrawerId) => {
    setOpenDrawer(drawer);
  }, []);

  const close = useCallback(() => {
    setOpenDrawer(null);
  }, []);

  const toggle = useCallback((drawer: DrawerId) => {
    setOpenDrawer((current) => (current === drawer ? null : drawer));
  }, []);

  const isOpen = useCallback(
    (drawer: DrawerId) => openDrawer === drawer,
    [openDrawer]
  );

  // ESC key closes drawer
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && openDrawer !== null) {
        setOpenDrawer(null);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [openDrawer]);

  return { openDrawer, open, close, toggle, isOpen };
}
