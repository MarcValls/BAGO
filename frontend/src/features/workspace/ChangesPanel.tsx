// src/features/workspace/ChangesPanel.tsx
// Lista de archivos modificados (dirty) con acciones: guardar, revertir, ver diff.

import type { OpenFileTab } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  tabs: OpenFileTab[];
  onSave: (path: string) => void;
  onRevert: (path: string) => void;
  onViewDiff: (path: string) => void;
  onSelect: (path: string) => void;
}

export function ChangesPanel(props: Props) {
  const dirty = props.tabs.filter((tab) => tab.state === 'dirty' || tab.state === 'saving' || tab.state === 'save_error');
  if (dirty.length === 0) {
    return <div className="workspace-panel-empty">Sin cambios sin guardar.</div>;
  }
  return (
    <ul className="workspace-changes">
      {dirty.map((tab) => (
        <li key={tab.path} className={`workspace-change state-${tab.state}`}>
          <button
            type="button"
            className="workspace-change-name"
            onClick={() => props.onSelect(tab.path)}
            title={tab.path}
          >
            <Icon name="file" size={11} /> {tab.label}
            <span className="workspace-change-state">{
              tab.state === 'dirty' ? 'modificado' :
              tab.state === 'saving' ? 'guardando' :
              'error al guardar'
            }</span>
          </button>
          <div className="workspace-change-actions">
            <button type="button" onClick={() => props.onSave(tab.path)} title="Guardar">
              <Icon name="check" size={11} /> Guardar
            </button>
            <button type="button" onClick={() => props.onRevert(tab.path)} title="Revertir">
              <Icon name="refresh" size={11} /> Revertir
            </button>
            <button type="button" onClick={() => props.onViewDiff(tab.path)} title="Ver diff">
              <Icon name="compare" size={11} /> Diff
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
