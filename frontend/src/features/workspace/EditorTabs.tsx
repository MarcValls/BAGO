// src/features/workspace/EditorTabs.tsx
// Tabs de archivos abiertos. Indicadores: dirty, error, en contexto.

import type { OpenFileTab } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  tabs: OpenFileTab[];
  activePath: string | null;
  onSelect: (path: string) => void;
  onClose: (path: string) => void;
}

export function EditorTabs(props: Props) {
  if (props.tabs.length === 0) {
    return <div className="workspace-editor-tabs empty">Sin archivos abiertos</div>;
  }
  return (
    <div className="workspace-editor-tabs" role="tablist">
      {props.tabs.map((tab) => {
        const isActive = tab.path === props.activePath;
        const hasError = tab.diagnostics.some((d) => d.severity === 'error');
        return (
          <div
            key={tab.path}
            role="tab"
            aria-selected={isActive}
            className={`workspace-editor-tab ${isActive ? 'is-active' : ''} state-${tab.state}`}
            onClick={() => props.onSelect(tab.path)}
            onAuxClick={(event) => {
              if (event.button === 1) {
                event.preventDefault();
                props.onClose(tab.path);
              }
            }}
            title={tab.path}
          >
            <span className={`workspace-editor-tab-flag state-${tab.state} ${hasError ? 'has-error' : ''}`} title={
              tab.state === 'dirty' ? 'Modificado sin guardar' :
              tab.state === 'saving' ? 'Guardando…' :
              tab.state === 'save_error' ? 'Error al guardar' :
              tab.state === 'readonly' ? 'Solo lectura' :
              hasError ? 'Con errores' :
              'Limpio'
            }>
              {hasError ? '!' : tab.state === 'dirty' || tab.state === 'saving' ? '●' : tab.state === 'save_error' ? '×' : tab.state === 'readonly' ? '🔒' : '·'}
            </span>
            <span className="workspace-editor-tab-name">{tab.label}</span>
            <button
              type="button"
              className="workspace-editor-tab-close"
              onClick={(event) => {
                event.stopPropagation();
                props.onClose(tab.path);
              }}
              aria-label={`Cerrar ${tab.label}`}
            >
              <Icon name="close" size={11} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
