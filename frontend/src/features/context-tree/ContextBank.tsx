// Banco contextual: lista compacta de piezas disponibles para añadir
// al árbol. Filtra por tipo, busca por texto, y soporta doble-click
// para añadir a la rama sugerida.
import { useMemo, useState } from 'react';
import type { ContextBankItem, ContextBankItemKind, ContextBankSnapshot, ContextNode } from './contextTreeTypes';
import { Icon, type IconName } from '@/shared/Icon';
import { SourceDirectoriesPanel } from './SourceDirectoriesPanel';

interface Props {
  bank: ContextBankSnapshot;
  loading: boolean;
  tree: ContextNode[]; // Lista plana de nodos del árbol (para "ir al nodo")
  onAddToTree: (item: ContextBankItem) => void;
  onOpenRelatedNode: (nodeId: string) => void;
  onReload: () => void;
  onAddToActivePack: (item: ContextBankItem) => void;
  // CANON[CTX-022]: alta/baja de items manuales del Banco. El usuario
  // introduce un path y se guarda como item persistido.
  onAddManualItem?: (path: string, kind: 'source_root' | 'workspace_file' | 'workspace_directory') => Promise<void>;
  onRemoveManualItem?: (itemId: string) => Promise<void>;
  // CANON[CTX-023]: gestión de directorios fuente. El usuario vincula
  // un directorio, ve sus archivos y decide cuáles incluir y a qué
  // rama del árbol asignarlos.
  sourceDirectories?: import('./contextTreeTypes').SourceDirectory[];
  sourceDirectoriesLoading?: boolean;
  onAddSourceDirectory?: (path: string) => Promise<void>;
  onRemoveSourceDirectory?: (id: string) => Promise<void>;
  onRefreshSourceDirectoryFiles?: (id: string) => Promise<void>;
  onToggleSourceFileInclude?: (id: string, filePath: string, include: boolean) => Promise<void>;
  onSetSourceFileBranch?: (id: string, filePath: string, branch: import('./contextTreeTypes').ContextNodeType) => Promise<void>;
  onLinkSourceDirectoryToTree?: (id: string) => Promise<void>;
}

type FilterValue = 'all' | ContextBankItemKind;

interface SectionDef {
  id: string;
  label: string;
  kind: ContextBankItemKind;
  icon: IconName;
  // CANON[CTX-024]: fase a la que pertenece la sección. Las secciones
  // de la misma fase se agrupan visualmente con un sub-encabezado.
  phase: 'linked' | 'available';
  getItems: (bank: ContextBankSnapshot) => ContextBankItem[];
}

// CANON[CTX-024]: dos fases visibles.
//   1. Fuentes vinculadas — lo que el usuario ha decidido
//      relacionar (manual + sources + directorios fuente).
//   2. Piezas disponibles — lo que el runtime expone (archivos,
//      claims, receipts, reglas, memoria, historial, proyecto).
const SECTIONS: SectionDef[] = [
  { id: 'sources', label: 'Fuentes', kind: 'source_root', icon: 'folder', phase: 'linked', getItems: (b) => b.sources },
  { id: 'manual', label: 'Añadidos', kind: 'source_root', icon: 'plus', phase: 'linked', getItems: (b) => b.manual },
  { id: 'files', label: 'Archivos', kind: 'workspace_file', icon: 'file', phase: 'available', getItems: (b) => b.files },
  { id: 'claims', label: 'Claims', kind: 'claim', icon: 'claim', phase: 'available', getItems: (b) => b.claims },
  { id: 'receipts', label: 'Receipts', kind: 'receipt', icon: 'evidence', phase: 'available', getItems: (b) => b.receipts },
  { id: 'rules', label: 'Reglas', kind: 'rule', icon: 'rule', phase: 'available', getItems: (b) => b.rules },
  { id: 'memory', label: 'Memoria', kind: 'memory', icon: 'session', phase: 'available', getItems: (b) => b.memory },
  { id: 'history', label: 'Historial', kind: 'history', icon: 'history', phase: 'available', getItems: (b) => b.history },
  { id: 'project', label: 'Proyecto', kind: 'project_status', icon: 'workspace', phase: 'available', getItems: (b) => b.project }
];

const FILTERS: Array<{ id: FilterValue; label: string }> = [
  { id: 'all', label: 'Todo' },
  { id: 'workspace_file', label: 'Archivos' },
  { id: 'workspace_directory', label: 'Carpetas' },
  { id: 'source_root', label: 'Fuentes' },
  { id: 'claim', label: 'Claims' },
  { id: 'receipt', label: 'Receipts' },
  { id: 'rule', label: 'Reglas' },
  { id: 'memory', label: 'Memoria' },
  { id: 'history', label: 'Historial' },
  { id: 'project_status', label: 'Proyecto' }
];

function getIconForKind(kind: ContextBankItemKind): IconName {
  switch (kind) {
    case 'workspace_file': return 'file';
    case 'workspace_directory': return 'folder';
    case 'source_root': return 'folder';
    case 'claim': return 'claim';
    case 'receipt': return 'evidence';
    case 'memory': return 'session';
    case 'history': return 'history';
    case 'rule': return 'rule';
    case 'project_status': return 'workspace';
    default: return 'node';
  }
}

export function ContextBank(props: Props) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<FilterValue>('all');
  const [filterOpen, setFilterOpen] = useState(false);
  const [actionMenuFor, setActionMenuFor] = useState<string | null>(null);
  const [manualPath, setManualPath] = useState('');
  const [manualKind, setManualKind] = useState<'source_root' | 'workspace_file' | 'workspace_directory'>('source_root');
  const [manualBusy, setManualBusy] = useState(false);

  const filteredSections = useMemo(() => {
    const q = query.trim().toLowerCase();
    return SECTIONS.map((section) => {
      let items = section.getItems(props.bank);
      if (filter !== 'all') {
        if (filter === 'workspace_file') {
          items = items.filter((item) => item.kind === 'workspace_file');
        } else if (filter === 'workspace_directory') {
          items = items.filter((item) => item.kind === 'workspace_directory');
        } else {
          items = items.filter((item) => item.kind === filter);
        }
      }
      if (q) {
        items = items.filter((item) => {
          const text = `${item.title} ${item.origin || ''} ${item.path || ''} ${(item.tags || []).join(' ')}`.toLowerCase();
          return text.includes(q);
        });
      }
      // CANON[CTX-025]: cap eliminado. El Banco se limita por la
      // búsqueda (query) y el filtro, no por un número arbitrario.
      // El usuario ve todos los items de cada fase; si la lista es
      // grande, el buscador es la herramienta principal de acceso.
      return { ...section, items };
    }).filter((section) => section.items.length > 0);
  }, [props.bank, query, filter]);

  const totalItems = filteredSections.reduce((acc, s) => acc + s.items.length, 0);

  return (
    <aside className="context-bank" aria-label="Banco contextual">
      <header className="context-bank-header">
        <span className="context-bank-title">
          <Icon name="tree" size={14} /> Contexto raíz
        </span>
        <span className="context-bank-count">{totalItems} piezas</span>
        <button
          type="button"
          className="icon-button"
          onClick={props.onReload}
          disabled={props.loading}
          title="Releer banco"
          aria-label="Releer banco"
        >
          <Icon name="refresh" size={13} />
        </button>
      </header>
      <div className="context-bank-search">
        <Icon name="search" size={12} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar pieza contextual…"
          aria-label="Buscar pieza contextual"
        />
        <details className="filter-dropdown" open={filterOpen} onToggle={(event) => setFilterOpen((event.currentTarget as HTMLDetailsElement).open)}>
          <summary title="Filtrar por tipo">
            <Icon name="filter" size={12} />
          </summary>
          <div className="filter-dropdown-menu" role="menu">
            {FILTERS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`filter-dropdown-item ${filter === opt.id ? 'is-active' : ''}`}
                onClick={() => { setFilter(opt.id); setFilterOpen(false); }}
              >
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        </details>
      </div>
      {props.onAddManualItem && (
        <form
          className="context-bank-manual"
          onSubmit={async (event) => {
            event.preventDefault();
            const path = manualPath.trim();
            if (!path || manualBusy) return;
            setManualBusy(true);
            try {
              await props.onAddManualItem?.(path, manualKind);
              setManualPath('');
            } finally {
              setManualBusy(false);
            }
          }}
        >
          <select
            value={manualKind}
            onChange={(event) => setManualKind(event.target.value as typeof manualKind)}
            aria-label="Tipo de path"
            title="Tipo de path"
          >
            <option value="source_root">Directorio / fuente</option>
            <option value="workspace_file">Archivo</option>
            <option value="workspace_directory">Carpeta</option>
          </select>
          <input
            value={manualPath}
            onChange={(event) => setManualPath(event.target.value)}
            placeholder="Ruta absoluta (ej. C:\Users\... o D:\proyectos\mi-carpeta)"
            aria-label="Ruta a vincular al árbol de contexto"
          />
          <button type="submit" disabled={manualBusy || !manualPath.trim()}>
            <Icon name="plus" size={11} /> Vincular
          </button>
        </form>
      )}
      {props.onAddSourceDirectory && props.sourceDirectories !== undefined && (
        <SourceDirectoriesPanel
          directories={props.sourceDirectories || []}
          loading={Boolean(props.sourceDirectoriesLoading)}
          onAdd={async (path) => { await props.onAddSourceDirectory?.(path); }}
          onRemove={async (id) => { await props.onRemoveSourceDirectory?.(id); }}
          onRefreshFiles={async (id) => { await props.onRefreshSourceDirectoryFiles?.(id); }}
          onToggleInclude={async (id, filePath, include) => { await props.onToggleSourceFileInclude?.(id, filePath, include); }}
          onSetBranch={async (id, filePath, branch) => { await props.onSetSourceFileBranch?.(id, filePath, branch); }}
          onLinkToTree={async (id) => { await props.onLinkSourceDirectoryToTree?.(id); }}
        />
      )}
      <div className="context-bank-list">
        {props.loading && totalItems === 0 && (
          <p className="context-bank-empty">Cargando piezas…</p>
        )}
        {!props.loading && totalItems === 0 && (
          <p className="context-bank-empty">
            No hay piezas disponibles. <button type="button" className="text-button" onClick={props.onReload}>Releer fuentes</button>
          </p>
        )}
        {(() => {
          const phaseLabels = { linked: 'Raíz vinculada', available: 'Raíz disponible' };
          const groups: Array<{ phase: 'linked' | 'available'; items: typeof filteredSections }> = [
            { phase: 'linked', items: filteredSections.filter((s) => s.phase === 'linked') },
            { phase: 'available', items: filteredSections.filter((s) => s.phase === 'available') }
          ];
          return groups.map((group) => (
            group.items.length > 0 && (
              <div key={group.phase} className="context-bank-phase">
                <header className="context-bank-phase-head">
                  <Icon name="folder" size={11} /> {phaseLabels[group.phase]}
                </header>
                {group.items.map((section) => (
                  <section key={section.id} className="context-bank-section">
            {section.items.map((item) => {
              const used = item.usedInTree ? props.tree.find((n) => n.id === item.usedInNodeId) : null;
              return (
                <article
                  key={item.id}
                  className={`context-bank-item ${used ? 'is-used' : ''}`}
                  tabIndex={0}
                  title={`${item.title}${item.path ? ` · ${item.path}` : ''}`}
                  onDoubleClick={() => props.onAddToTree(item)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      props.onAddToTree(item);
                    }
                  }}
                >
                  <header>
                    <span className="context-bank-item-icon"><Icon name={getIconForKind(item.kind)} size={11} /></span>
                    <span className="context-bank-item-title">{item.title}</span>
                    {used && (
                      <button
                        type="button"
                        className="text-button context-bank-item-used"
                        onClick={(event) => {
                          event.stopPropagation();
                          if (used.id) props.onOpenRelatedNode(used.id);
                        }}
                        title="Ir al nodo en el árbol"
                      >
                        <Icon name="link" size={10} /> usado
                      </button>
                    )}
                  </header>
                  <p className="context-bank-item-meta">
                    {item.origin}
                    {item.path ? ` · ${item.path}` : ''}
                    {item.weightTokens ? ` · ${item.weightTokens}t` : ''}
                  </p>
                  <footer>
                    <button
                      type="button"
                      className="text-button"
                      onClick={(event) => { event.stopPropagation(); props.onAddToTree(item); }}
                      title="Añadir esta pieza al árbol"
                    >
                      <Icon name="plus" size={10} /> al árbol
                    </button>
                    <button
                      type="button"
                      className="text-button"
                      onClick={(event) => { event.stopPropagation(); props.onAddToActivePack(item); }}
                      title={item.kind === 'workspace_directory' ? 'Añadir este directorio al pack' : item.kind === 'workspace_file' ? 'Añadir este archivo al pack' : 'Añadir esta pieza al pack'}
                    >
                      <Icon name="pack" size={10} /> {item.kind === 'workspace_directory' ? 'dir. al pack' : item.kind === 'workspace_file' ? 'archivo al pack' : 'pieza al pack'}
                    </button>
                    <button
                      type="button"
                      className="icon-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setActionMenuFor((current) => current === item.id ? null : item.id);
                      }}
                      title="Más acciones"
                      aria-label="Más acciones"
                    >
                      <Icon name="more" size={12} />
                    </button>
                  </footer>
                  {actionMenuFor === item.id && (
                    <div className="context-bank-item-menu" role="menu">
                      <button type="button" onClick={() => { props.onAddToTree(item); setActionMenuFor(null); }}>
                        <Icon name="plus" size={11} /> Añadir al árbol
                      </button>
                      {item.kind === 'rule' && (
                        <button type="button" onClick={() => { props.onAddToTree({ ...item, suggestedBranch: 'rule' }); setActionMenuFor(null); }}>
                          <Icon name="rule" size={11} /> Añadir como regla
                        </button>
                      )}
                      {item.kind === 'claim' && (
                        <button type="button" onClick={() => { props.onAddToTree({ ...item, suggestedBranch: 'evidence' }); setActionMenuFor(null); }}>
                          <Icon name="claim" size={11} /> Añadir como evidencia
                        </button>
                      )}
                      {(item.kind === 'workspace_file' || item.kind === 'workspace_directory') && (
                        <button type="button" onClick={() => { navigator.clipboard?.writeText(item.path || item.title); setActionMenuFor(null); }}>
                          <Icon name="copy" size={11} /> Copiar ruta
                        </button>
                      )}
                      {item.id && (
                        <button type="button" onClick={() => { navigator.clipboard?.writeText(item.id); setActionMenuFor(null); }}>
                          <Icon name="copy" size={11} /> Copiar ID
                        </button>
                      )}
                      {item.kind === 'source_root' && item.id?.startsWith('manual:') && props.onRemoveManualItem && (
                        <button type="button" onClick={() => { void props.onRemoveManualItem?.(item.id); setActionMenuFor(null); }}>
                          <Icon name="close" size={11} /> Quitar de añadidos
                        </button>
                      )}
                    </div>
                  )}
                </article>
              );
            })}
                  </section>
                ))}
              </div>
            )
          ));
        })()}
      </div>
      {props.bank.errors.length > 0 && (
        <footer className="context-bank-errors">
          <details>
            <summary>Errores de carga ({props.bank.errors.length})</summary>
            <ul>
              {props.bank.errors.map((err, idx) => <li key={idx}>{err}</li>)}
            </ul>
          </details>
        </footer>
      )}
    </aside>
  );
}
