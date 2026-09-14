// src/features/workspace/WorkspaceToolbar.tsx
// Toolbar compacta: buscador, filtro, workspace, guardar, ⋯.

import { useState } from 'react';
import type { WorkspaceFilter } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

const FILTER_LABELS: Record<WorkspaceFilter, string> = {
  all: 'Todo',
  code: 'Código',
  python: 'Python',
  typescript: 'TypeScript',
  javascript: 'JavaScript',
  json: 'JSON',
  markdown: 'Markdown',
  shell: 'Shell',
  web: 'Web',
  text: 'Texto',
  directory: 'Carpetas',
  'with-errors': 'Con errores'
};

const FILTER_ORDER: WorkspaceFilter[] = [
  'all', 'code', 'python', 'typescript', 'javascript', 'json', 'markdown', 'shell', 'web', 'text', 'directory', 'with-errors'
];

interface ToolbarProps {
  query: string;
  onQueryChange: (query: string) => void;
  filter: WorkspaceFilter;
  onFilterChange: (filter: WorkspaceFilter) => void;
  workspaceLabel: string;
  workspaceTitle: string;
  onChooseWorkspace: () => void;
  onRunCommand: (command: string) => void;
  onPersist: () => void;
  onSync: () => void;
  onCopyPath: () => void;
  onOpenExternal: () => void;
  onStatus: () => void;
  hasDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onSaveAll: () => void;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onReread: () => void;
  onToggleBottom: (panel: 'problems' | 'changes' | 'patterns' | 'output') => void;
}

export function WorkspaceToolbar(props: ToolbarProps) {
  const [filterOpen, setFilterOpen] = useState(false);
  const [wsMenuOpen, setWsMenuOpen] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);

  const filterLabel = FILTER_LABELS[props.filter];

  return (
    <div className="workspace-toolbar" role="toolbar" aria-label="Barra de herramientas del workspace">
      <label className="surface-search workspace-toolbar-search">
        <Icon name="search" size={14} />
        <input
          value={props.query}
          onChange={(event) => props.onQueryChange(event.target.value)}
          placeholder="Buscar archivo, ruta, símbolo o extensión"
          aria-label="Buscar archivo, ruta o extensión"
        />
      </label>

      <div className="filter-dropdown">
        <button
          type="button"
          className={`filter-dropdown-trigger ${props.filter !== 'all' ? 'is-active' : ''}`}
          onClick={() => setFilterOpen((v) => !v)}
          aria-expanded={filterOpen}
        >
          <Icon name="filter" size={13} />
          <span>Filtro: {filterLabel}</span>
          <Icon name="chevron" size={11} />
        </button>
        {filterOpen && (
          <div className="filter-dropdown-menu" role="listbox">
            {FILTER_ORDER.map((f) => (
              <button
                key={f}
                type="button"
                role="option"
                aria-selected={f === props.filter}
                className={`filter-dropdown-item ${f === props.filter ? 'is-selected' : ''}`}
                onClick={() => {
                  props.onFilterChange(f);
                  setFilterOpen(false);
                }}
              >
                {FILTER_LABELS[f]}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="workspace-menu-button">
        <button
          type="button"
          className="workspace-menu-button-trigger"
          onClick={() => setWsMenuOpen((v) => !v)}
          aria-expanded={wsMenuOpen}
          title={props.workspaceTitle}
        >
          <Icon name="folder" size={13} />
          <span>{props.workspaceLabel}</span>
          <Icon name="chevron" size={11} />
        </button>
        {wsMenuOpen && (
          <div className="workspace-menu-button-menu" role="menu">
            <button type="button" onClick={() => { props.onChooseWorkspace(); setWsMenuOpen(false); }}>
              <Icon name="folder" size={12} /> Cambiar workspace
            </button>
            <button type="button" onClick={() => { props.onPersist(); setWsMenuOpen(false); }}>
              <Icon name="check" size={12} /> Persistir
            </button>
            <button type="button" onClick={() => { props.onSync(); setWsMenuOpen(false); }}>
              <Icon name="refresh" size={12} /> Sincronizar
            </button>
            <button type="button" onClick={() => { props.onCopyPath(); setWsMenuOpen(false); }}>
              <Icon name="copy" size={12} /> Copiar ruta
            </button>
            <button type="button" onClick={() => { props.onOpenExternal(); setWsMenuOpen(false); }}>
              <Icon name="arrowRight" size={12} /> Abrir carpeta externa
            </button>
            <button type="button" onClick={() => { props.onStatus(); setWsMenuOpen(false); }}>
              <Icon name="inspector" size={12} /> Ver estado
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        className={`toolbar-save-button state-${props.isSaving ? 'saving' : (props.hasDirty ? 'dirty' : 'clean')}`}
        onClick={() => props.onSave()}
        disabled={!props.hasDirty}
        title={props.hasDirty ? 'Guardar archivo activo' : 'Sin cambios'}
      >
        <Icon name="check" size={13} />
        <span>{props.isSaving ? 'Guardando…' : props.hasDirty ? 'Guardar' : 'Guardado'}</span>
      </button>

      <div className="workspace-actions-menu">
        <button
          type="button"
          className="workspace-actions-menu-trigger"
          onClick={() => setActionsOpen((v) => !v)}
          aria-expanded={actionsOpen}
          aria-label="Más acciones"
        >
          <Icon name="more" size={14} />
        </button>
        {actionsOpen && (
          <div className="workspace-actions-menu-items" role="menu">
            <button type="button" onClick={() => { props.onExpandAll(); setActionsOpen(false); }}>
              <Icon name="expand" size={12} /> Expandir árbol
            </button>
            <button type="button" onClick={() => { props.onCollapseAll(); setActionsOpen(false); }}>
              <Icon name="collapse" size={12} /> Contraer árbol
            </button>
            <button type="button" onClick={() => { props.onReread(); setActionsOpen(false); }}>
              <Icon name="refresh" size={12} /> Releer archivos
            </button>
            <button type="button" onClick={() => { props.onToggleBottom('problems'); setActionsOpen(false); }}>
              <Icon name="alert" size={12} /> Ver problemas
            </button>
            <button type="button" onClick={() => { props.onToggleBottom('patterns'); setActionsOpen(false); }}>
              <Icon name="inspector" size={12} /> Ver patrones
            </button>
            <button type="button" onClick={() => { props.onSaveAll(); setActionsOpen(false); }}>
              <Icon name="check" size={12} /> Guardar todo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
