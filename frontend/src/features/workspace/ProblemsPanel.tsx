// src/features/workspace/ProblemsPanel.tsx
// Lista de diagnósticos por archivo, agrupados por severidad.
// Click → salta a la línea.

import type { OpenFileTab, WorkspaceDiagnostic } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  tabs: OpenFileTab[];
  onJump: (path: string, line: number) => void;
  onOpenInContext: (diagnostic: WorkspaceDiagnostic) => void;
  onSendToChat: (diagnostic: WorkspaceDiagnostic) => void;
  onCreatePlan: (diagnostic: WorkspaceDiagnostic) => void;
  onIgnore: (diagnosticId: string) => void;
  ignoredIds: Set<string>;
}

const SEVERITY_ORDER: Record<WorkspaceDiagnostic['severity'], number> = {
  error: 0,
  warning: 1,
  info: 2,
  hint: 3
};

export function ProblemsPanel(props: Props) {
  const visible: Array<{ tab: OpenFileTab; diagnostic: WorkspaceDiagnostic }> = [];
  for (const tab of props.tabs) {
    for (const diagnostic of tab.diagnostics) {
      if (props.ignoredIds.has(diagnostic.id)) continue;
      visible.push({ tab, diagnostic });
    }
  }
  visible.sort((a, b) => SEVERITY_ORDER[a.diagnostic.severity] - SEVERITY_ORDER[b.diagnostic.severity]);

  if (visible.length === 0) {
    return <div className="workspace-panel-empty">Sin problemas detectados.</div>;
  }
  const errors = visible.filter((v) => v.diagnostic.severity === 'error').length;
  const warnings = visible.filter((v) => v.diagnostic.severity === 'warning').length;
  return (
    <div className="workspace-problems">
      <header className="workspace-panel-summary">
        <span><Icon name="alert" size={12} /> {errors} errores · {warnings} warnings</span>
      </header>
      <ul className="workspace-problems-list">
        {visible.map(({ tab, diagnostic }) => (
          <li key={diagnostic.id} className={`workspace-problem severity-${diagnostic.severity}`}>
            <button
              type="button"
              className="workspace-problem-jump"
              onClick={() => props.onJump(tab.path, diagnostic.startLine)}
            >
              <span className="workspace-problem-severity">{diagnostic.severity}</span>
              <span className="workspace-problem-location">{tab.label}:{diagnostic.startLine}:{diagnostic.startColumn}</span>
              <span className="workspace-problem-message">{diagnostic.message}</span>
            </button>
            <div className="workspace-problem-actions">
              <button type="button" onClick={() => props.onOpenInContext(diagnostic)} title="Añadir como riesgo al Árbol de Contexto">
                <Icon name="risk" size={11} /> Riesgo
              </button>
              <button type="button" onClick={() => props.onSendToChat(diagnostic)} title="Enviar al Chat">
                <Icon name="send" size={11} /> Chat
              </button>
              <button type="button" onClick={() => props.onCreatePlan(diagnostic)} title="Crear tarea en Pipeline">
                <Icon name="pipeline" size={11} /> Tarea
              </button>
              <button type="button" onClick={() => props.onIgnore(diagnostic.id)} title="Ignorar">
                <Icon name="close" size={11} /> Ignorar
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
