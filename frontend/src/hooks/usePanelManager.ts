import { useState, useCallback, useEffect } from 'react';
import type { PanelId } from '../contracts/backend';

interface UsePanelManagerReturn {
  openDrawer: PanelId | null;
  open: (drawer: PanelId) => void;
  close: () => void;
  toggle: (drawer: PanelId) => void;
  isOpen: (drawer: PanelId) => boolean;
}

export function usePanelManager(): UsePanelManagerReturn {
  const [openDrawer, setOpenDrawer] = useState<PanelId | null>(null);

  const open = useCallback((drawer: PanelId) => {
    setOpenDrawer(drawer);
  }, []);

  const close = useCallback(() => {
    setOpenDrawer(null);
  }, []);

  const toggle = useCallback((drawer: PanelId) => {
    setOpenDrawer((current) => (current === drawer ? null : drawer));
  }, []);

  const isOpen = useCallback(
    (drawer: PanelId) => openDrawer === drawer,
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
