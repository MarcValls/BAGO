import type { OpeningDecision, UiBootstrapSnapshot } from '@/contracts/backend';

export function resolveOpeningState(snapshot: UiBootstrapSnapshot | null): OpeningDecision {
  if (!snapshot) {
    return {
      id: 'show_blocked_state',
      label: 'Conectando con el backend',
      reason: 'El panel todavía no ha recibido el estado operativo.',
      actionLabel: 'Reintentar conexión',
      targetSection: 'home'
    };
  }

  if (!snapshot.system.backendAvailable || snapshot.system.state === 'error') {
    return {
      id: 'show_blocked_state',
      label: 'Backend no disponible',
      reason: 'La API de BAGO no devolvió un estado utilizable.',
      actionLabel: 'Revisar backend',
      targetSection: 'system'
    };
  }

  if (snapshot.workspace.manifestState === 'legacy') {
    return {
      id: 'show_legacy_migration',
      label: 'Workspace antiguo detectado',
      reason: 'Existe un workspace .bago antiguo que debe revisarse antes de continuar.',
      actionLabel: 'Revisar migración',
      targetSection: 'workspace'
    };
  }

  if (snapshot.workspace.manifestState === 'invalid' || snapshot.session.state === 'blocked') {
    return {
      id: 'show_workspace_repair',
      label: 'El workspace necesita reparación',
      reason: 'El backend informa de una vinculación no válida o una sesión bloqueada.',
      actionLabel: 'Abrir reparación',
      targetSection: 'workspace'
    };
  }

  if (!snapshot.workspace.root || snapshot.project.state === 'not_detected') {
    return {
      id: 'show_workspace_init',
      label: 'No hay workspace activo',
      reason: 'El backend no informó de una raíz de proyecto activa.',
      actionLabel: 'Inicializar workspace',
      targetSection: 'home'
    };
  }

  if (snapshot.system.state === 'degraded' || snapshot.context.state === 'stale') {
    return {
      id: 'show_recovery',
      label: 'Se recomienda recuperar el estado',
      reason: 'La sesión es válida, pero algunas señales están limitadas o desactualizadas.',
      actionLabel: 'Abrir recuperación',
      targetSection: 'home'
    };
  }

  if (snapshot.workspace.linkedToSession && snapshot.session.state === 'valid') {
    return {
      id: 'enter_directly',
      label: 'Workspace vinculado',
      reason: 'El backend confirma que la sesión y el workspace están vinculados.',
      actionLabel: 'Abrir conversación',
      targetSection: 'home'
    };
  }

  if (snapshot.workspace.root && !snapshot.workspace.linkedToSession) {
    return {
      id: 'show_workspace_link',
      label: 'Workspace listo para vincular',
      reason: 'El workspace existe, pero todavía no está vinculado a la sesión.',
      actionLabel: 'Vincular y preparar',
      targetSection: 'home'
    };
  }

  return {
    id: 'show_recovery',
    label: 'Se recomienda recuperar el estado',
    reason: 'El estado del backend es ambiguo; BAGO abrirá el modo de recuperación.',
    actionLabel: 'Abrir recuperación',
    targetSection: 'home'
  };
}
