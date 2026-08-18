// src/features/workspace/PatternsPanel.tsx
// Lista de patrones detectados con acciones contextuales.

import type { OpenFileTab, WorkspacePattern } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  tabs: OpenFileTab[];
  onJump: (path: string, line: number) => void;
  onSendToChat: (tab: OpenFileTab, pattern: WorkspacePattern) => void;
  onAddAsRisk: (tab: OpenFileTab, pattern: WorkspacePattern) => void;
  onAddAsPending: (tab: OpenFileTab, pattern: WorkspacePattern) => void;
  onAddAsRule: (tab: OpenFileTab, pattern: WorkspacePattern) => void;
  onCreatePlan: (tab: OpenFileTab, pattern: WorkspacePattern) => void;
}

const CATEGORY_LABEL: Record<WorkspacePattern['category'], string> = {
  code: 'Código',
  ui: 'UI',
  bago: 'BAGO',
  security: 'Seguridad'
};

export function PatternsPanel(props: Props) {
  const all: Array<{ tab: OpenFileTab; pattern: WorkspacePattern }> = [];
  for (const tab of props.tabs) {
    for (const pattern of tab.patterns) {
      all.push({ tab, pattern });
    }
  }
  if (all.length === 0) {
    return <div className="workspace-panel-empty">Sin patrones relevantes.</div>;
  }
  return (
    <ul className="workspace-patterns">
      {all.map(({ tab, pattern }) => (
        <li key={pattern.id} className={`workspace-pattern severity-${pattern.severity} category-${pattern.category}`}>
          <button
            type="button"
            className="workspace-pattern-jump"
            onClick={() => props.onJump(tab.path, pattern.startLine)}
          >
            <span className="workspace-pattern-category">{CATEGORY_LABEL[pattern.category]}</span>
            <span className="workspace-pattern-title">{pattern.title}</span>
            <span className="workspace-pattern-location">{tab.label}:{pattern.startLine}</span>
          </button>
          <div className="workspace-pattern-actions">
            <button type="button" onClick={() => props.onSendToChat(tab, pattern)} title="Enviar al Chat">
              <Icon name="send" size={11} /> Chat
            </button>
            <button type="button" onClick={() => props.onCreatePlan(tab, pattern)} title="Crear tarea">
              <Icon name="pipeline" size={11} /> Tarea
            </button>
            <button type="button" onClick={() => props.onAddAsRisk(tab, pattern)} title="Añadir como riesgo">
              <Icon name="risk" size={11} /> Riesgo
            </button>
            <button type="button" onClick={() => props.onAddAsPending(tab, pattern)} title="Añadir como pendiente">
              <Icon name="inbox" size={11} /> Pendiente
            </button>
            <button type="button" onClick={() => props.onAddAsRule(tab, pattern)} title="Añadir como regla">
              <Icon name="rule" size={11} /> Regla
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
