import type { SystemState, UiBootstrapSnapshot } from '@/contracts/backend';

export interface WorkspaceAuthority {
  state: SystemState;
  label: string;
  requiresAction: boolean;
  reason: string;
  projectLabel: string;
  projectRoot: string;
}

export function canPersistWorkspaceAuthority(snapshot: UiBootstrapSnapshot | null): boolean {
  return Boolean(
    snapshot
    && snapshot.workspace.linkedToSession
    && snapshot.workspace.manifestState === 'valid'
  );
}

function basename(path: string): string {
  const clean = path.trim().replace(/[\\/]+$/, '');
  return clean.split(/[\\/]/).filter(Boolean).pop() || '';
}

export function explainWorkspaceBinding(reason: string): string {
  const value = reason.toLowerCase();
  if (value.includes('scope mismatch') || value.includes('project mismatch')) {
    return 'El proyecto seleccionado no coincide con el manifiesto del workspace.';
  }
  if (value.includes('legacy')) {
    return 'El workspace usa una estructura anterior y necesita migración.';
  }
  if (value.includes('manifest')) {
    return 'El manifiesto del workspace no es válido.';
  }
  return reason.trim() || 'Selecciona un proyecto válido para continuar.';
}

export function resolveWorkspaceAuthority(snapshot: UiBootstrapSnapshot | null): WorkspaceAuthority {
  if (!snapshot) {
    return {
      state: 'loading', label: 'Comprobando', requiresAction: false,
      reason: 'Consultando el backend activo.', projectLabel: 'Sin proyecto', projectRoot: ''
    };
  }
  if (!snapshot.system.backendAvailable) {
    return {
      state: 'error', label: 'Backend sin conexión', requiresAction: true,
      reason: 'BAGO no puede confirmar el estado del proyecto.', projectLabel: 'Sin proyecto', projectRoot: ''
    };
  }

  const projectRoot = String(snapshot.project.root || snapshot.workspace.repoRoot || snapshot.workspace.scopeRoot || '').trim();
  const valid = snapshot.workspace.linkedToSession && snapshot.workspace.manifestState === 'valid';
  if (!valid) {
    const label = snapshot.workspace.manifestState === 'missing' ? 'Proyecto sin preparar' : 'Workspace requiere atención';
    return {
      state: 'blocked', label, requiresAction: true,
      reason: explainWorkspaceBinding(snapshot.workspace.bindingReason || snapshot.system.bindingReason || ''),
      projectLabel: basename(projectRoot) || 'Sin proyecto válido', projectRoot
    };
  }

  return {
    state: snapshot.system.state,
    label: snapshot.system.state === 'confirmed' ? 'Operativo' : snapshot.system.state === 'degraded' ? 'Limitado' : 'Estado pendiente',
    requiresAction: false,
    reason: '',
    projectLabel: basename(projectRoot) || snapshot.workspace.id || 'Proyecto activo',
    projectRoot
  };
}
