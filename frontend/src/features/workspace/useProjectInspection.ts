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

export interface ProjectInspectionAction {
  kind: 'open' | 'link' | 'prepare' | 'unavailable';
  label: string;
  detail: string;
  seed: boolean;
}

const DEFAULT_STATE: ProjectInspectionState = { kind: 'idle' };

/**
 * Maps the filesystem inspection to the one operation that is safe to offer
 * next. `prepare` is explicit because it may create the missing BAGO files.
 */
export function projectInspectionAction(inspection: ProjectInspectionState): ProjectInspectionAction {
  if (inspection.kind === 'loading') {
    return { kind: 'unavailable', label: 'Inspeccionando…', detail: 'BAGO está comprobando esta carpeta antes de proponer una acción.', seed: false };
  }
  if (inspection.kind === 'error') {
    return { kind: 'unavailable', label: 'No se pudo inspeccionar', detail: inspection.message || 'Corrige la ruta o vuelve a intentarlo.', seed: false };
  }
  if (inspection.kind !== 'ready') {
    return { kind: 'unavailable', label: 'Selecciona una carpeta', detail: 'Elige una carpeta para comprobar su estado.', seed: false };
  }
  if (inspection.configured && inspection.linked && inspection.bindingConfirmed) {
    return { kind: 'open', label: 'Abrir workspace', detail: 'Esta carpeta ya está configurada y vinculada a BAGO.', seed: false };
  }
  if (inspection.configured && !inspection.linked) {
    return { kind: 'link', label: 'Vincular workspace', detail: 'La carpeta ya tiene la configuración de BAGO; falta vincularla.', seed: false };
  }
  return {
    kind: 'prepare',
    label: 'Preparar workspace',
    detail: inspection.bindingReason || 'BAGO creará los archivos de workspace que falten antes de activarlo.',
    seed: true
  };
}

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
