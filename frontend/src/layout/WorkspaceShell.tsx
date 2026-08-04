import type { ReactNode } from 'react';
import type { ActiveSection, UiBootstrapSnapshot } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';

const copy: Record<ActiveSection, { title: string; eyebrow: string; description: string }> = {
  home: { title: 'Inicio', eyebrow: 'Chat', description: 'Elige si vas a empezar algo nuevo o continuar un proyecto.' },
  chat: { title: 'Conversación', eyebrow: 'Chat', description: 'Panel lateral para preguntar, decidir y ejecutar.' },
  workspace: { title: 'Workspace', eyebrow: 'Trabajo estructurado', description: 'Archivos, fuentes y alcance autorizado.' },
  graph: { title: 'Grafo', eyebrow: 'Relaciones', description: 'Mapa operativo de sesión, contexto, workspace y evidencia.' },
  pipeline: { title: 'Pipeline', eyebrow: 'Ejecución', description: 'Pasos, jobs, bloqueos y evidencias asociadas.' },
  evidence: { title: 'Evidencia', eyebrow: 'Trazabilidad', description: 'Receipts, claims e historial verificable.' },
  context: { title: 'Contexto', eyebrow: 'Presupuesto', description: 'Uso, reserva, límite y factor limitante.' },
  system: { title: 'Operación', eyebrow: 'Sistema', description: 'Router, proveedores, runtime y rutas API.' }
};

interface Props {
  activeSection: ActiveSection;
  snapshot: UiBootstrapSnapshot | null;
  mode: 'normal' | 'focus' | 'review';
  /**
   * Muestra la franja de readiness (Preparación 67%). Por defecto true.
   * Pasar `false` en secciones donde la readiness es ruido (Workspace)
   * y se sustituye por un avisador compacto en la propia superficie.
   */
  showReadiness?: boolean;
  /**
   * Muestra los chips de contexto / modelo / workspace.id en el header.
   * Por defecto true. Pasar `false` cuando la sección ya tiene su propio
   * marcador de estado (ej. Workspace, que prefiere mostrar solo su id
   * local y evita duplicar lo que ya está en el Topbar global).
   */
  showGlobalChips?: boolean;
  children: ReactNode;
}

function shellState(snapshot: UiBootstrapSnapshot | null): string {
  if (!snapshot) return '';
  if (!snapshot.system.backendAvailable) return 'Backend offline';
  if (!snapshot.workspace.linkedToSession) return 'Workspace pendiente';
  if (snapshot.context.state === 'blocked') return 'Contexto bloqueado';
  return '';
}

function tone(value: boolean | string | undefined): string {
  if (value === true) return 'confirmed';
  const text = String(value || '').toLowerCase();
  if (['confirmed', 'valid', 'ok', 'active', 'certified'].some((item) => text.includes(item))) return 'confirmed';
  if (['partial', 'running', 'loading', 'stale', 'pending', 'recoverable'].some((item) => text.includes(item))) return 'running';
  if (['error', 'invalid', 'failed'].some((item) => text.includes(item))) return 'error';
  if (['blocked', 'missing', 'offline'].some((item) => text.includes(item))) return 'blocked';
  return 'unknown';
}

export function WorkspaceShell(props: Props) {
  const meta = copy[props.activeSection];
  const workspace = props.snapshot?.workspace.id || props.snapshot?.workspace.root || 'Sin workspace';
  const model = props.snapshot?.model.effectiveModel || props.snapshot?.model.configuredModel || 'Sin modelo';
  const state = shellState(props.snapshot);
  const stages = [
    { label: 'Workspace', value: props.snapshot?.workspace.linkedToSession ? 'vinculado' : props.snapshot?.workspace.manifestState || 'pendiente', state: props.snapshot?.workspace.linkedToSession ? 'confirmed' : props.snapshot?.workspace.manifestState },
    { label: 'Contexto', value: props.snapshot?.context.receiptId || props.snapshot?.context.state || 'sin receipt', state: props.snapshot?.context.state },
    { label: 'Modelo', value: props.snapshot?.model.effectiveModel || props.snapshot?.model.provider || 'sin modelo', state: props.snapshot?.model.state }
  ];
  const confirmed = stages.filter((stage) => tone(stage.state) === 'confirmed').length;
  const readiness = Math.round((confirmed / stages.length) * 100);
  const isContext = props.activeSection === 'context';

  return (
    <section className={`workspace-shell mode-${props.mode} section-${props.activeSection}`} data-section={props.activeSection}>
      {props.mode !== 'focus' && (props.showReadiness !== false || props.showGlobalChips !== false) && (
        <header className="workspace-shell-header is-compact" aria-label={`Estado operativo de ${meta.title}`}>
          {props.showReadiness !== false && (
            <div className="workspace-readiness" aria-label={`Preparación operativa ${readiness}%`}>
              <div className="workspace-readiness-head">
                <span>Preparación</span>
                <strong>{readiness}%</strong>
              </div>
              <div className="workspace-readiness-bar"><span style={{ width: `${readiness}%` }} /></div>
              <div className="workspace-readiness-stages">
                {stages.map((stage) => (
                  <span key={stage.label} className={`readiness-stage state-${tone(stage.state)}`} title={stage.value}>
                    <i /> {stage.label}
                  </span>
                ))}
              </div>
            </div>
          )}
          {!isContext && <div className="workspace-shell-meta" aria-label="Resumen del estado">
            {props.showGlobalChips !== false && (
              <>
                {state && (
                  <span className={`workspace-shell-chip state-${props.snapshot?.system.state || 'unknown'}`}>
                    <Icon name="system" size={14} /> {state}
                  </span>
                )}
                <span className="workspace-shell-chip" title={workspace}>
                  <Icon name="workspace" size={14} /> {workspace}
                </span>
                <span className="workspace-shell-chip" title={model}>
                  <Icon name="model" size={14} /> {model}
                </span>
              </>
            )}
          </div>}
        </header>
      )}
      <div className="surface-body">{props.children}</div>
      {isContext && props.showGlobalChips !== false && (
        <footer className="workspace-shell-footer" aria-label="Estado del contexto de trabajo">
          {state && <span className={`workspace-shell-chip state-${props.snapshot?.system.state || 'unknown'}`}><Icon name="system" size={12} /> {state}</span>}
          <span className="workspace-shell-chip" title={workspace}><Icon name="workspace" size={12} /> {workspace}</span>
          <span className="workspace-shell-chip" title={model}><Icon name="model" size={12} /> {model}</span>
        </footer>
      )}
    </section>
  );
}
