import { useEffect, useState } from 'react';
import type { BagoClient } from '@/api/client';
import type { UiBootstrapSnapshot } from '@/contracts/backend';

/**
 * CANON[CHAT-DOCK]: seguimiento del proveedor activo y sus modelos
 * activos. Se usa tanto en ControlPlane (chat acoplado) como en
 * ControlSections (chat pantalla completa) para que el selector de
 * modelo resalte la misma selección en ambos modos.
 */
export function useActiveProviderModels(client: BagoClient | null, snapshot: UiBootstrapSnapshot | null): {
  activeProvider: string | null;
  activeModels: Set<string>;
} {
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [activeModels, setActiveModels] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!client) {
      setActiveProvider(null);
      setActiveModels(new Set());
      return;
    }
    const rawSnapshot = snapshot as Record<string, unknown> | null;
    const model = rawSnapshot?.model as Record<string, unknown> | undefined;
    const session = rawSnapshot?.session as Record<string, unknown> | undefined;
    const system = rawSnapshot?.system as Record<string, unknown> | undefined;
    const provider = model?.provider
      || rawSnapshot?.provider
      || session?.provider
      || system?.provider
      || null;
    if (!provider || typeof provider !== 'string') {
      setActiveProvider(null);
      setActiveModels(new Set());
      return;
    }
    setActiveProvider(provider);
    client.getActiveProviderModels(provider)
      .then((data) => {
        if (Array.isArray(data.active_models)) {
          setActiveModels(new Set(data.active_models));
        } else {
          setActiveModels(new Set());
        }
      })
      .catch(() => setActiveModels(new Set()));
  }, [client, snapshot]);

  return { activeProvider, activeModels };
}
