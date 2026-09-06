import { useEffect, useState } from 'react';
import type { BagoClient } from '@/api/client';

export interface ProjectInspectionState {
  kind: 'idle' | 'loading' | 'error' | 'ready';
  configured?: boolean;
  linked?: boolean;
  bindingConfirmed?: boolean;
  bindingReason?: string;
  message?: string;
}

const DEFAULT_STATE: ProjectInspectionState = { kind: 'idle' };

/**
 * Reusable project inspection hook.
 * Debounces path changes and inspects via POST /project/inspect.
 * Used by WorkspacePickerDialog and FirstRunWizard to show
 * contextual state without requiring the user to guess.
 */
export function useProjectInspection(
  path: string,
  client: BagoClient,
  debounceMs = 300
): ProjectInspectionState {
  const [state, setState] = useState<ProjectInspectionState>(DEFAULT_STATE);

  useEffect(() => {
    const clean = path.trim();
    if (!clean) {
      setState(DEFAULT_STATE);
      return;
    }
    let cancelled = false;
    setState({ kind: 'loading' });
    const timer = window.setTimeout(async () => {
      try {
        const data = await client.inspectProject(clean);
        if (cancelled) return;
        setState({
          kind: 'ready',
          configured: Boolean(data.configured),
          linked: Boolean(data.linked),
          bindingConfirmed: Boolean(data.binding_confirmed),
          bindingReason: String(data.binding_reason || '')
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : 'Error al inspeccionar'
        });
      }
    }, debounceMs);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [path, client, debounceMs]);

  return state;
}
