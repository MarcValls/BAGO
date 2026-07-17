// src/features/context-tree/SourceDirectoriesPanel.tsx
// CANON[CTX-023]: superficie de gestión de directorios fuente. Lista
// los directorios vinculados por el usuario, sus archivos y permite
// decidir cuáles incluir y a qué rama del árbol asignarlos.

import { useState } from 'react';
import type { ContextNodeType, SourceDirectory } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';

const BRANCH_LABELS: Array<{ value: ContextNodeType; label: string }> = [
  { value: 'intent', label: 'Intención' },
  { value: 'source', label: 'Fuentes' },
  { value: 'decision', label: 'Decisiones' },
  { value: 'rule', label: 'Reglas' },
  { value: 'risk', label: 'Riesgos' },
  { value: 'pending', label: 'Pendientes' },
  { value: 'evidence', label: 'Evidencias' },
  { value: 'claim', label: 'Claims' },
  { value: 'file', label: 'Archivos' },
  { value: 'note', label: 'Notas' }
];

interface Props {
  directories: SourceDirectory[];
  loading: boolean;
  onAdd: (path: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  onRefreshFiles: (id: string) => Promise<void>;
  onToggleInclude: (id: string, filePath: string, include: boolean) => Promise<void>;
  onSetBranch: (id: string, filePath: string, branch: ContextNodeType) => Promise<void>;
  onLinkToTree: (id: string) => Promise<void>;
}

export function SourceDirectoriesPanel(props: Props) {
  const [newPath, setNewPath] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [linkingId, setLinkingId] = useState<string | null>(null);

  const handleAdd = async () => {
    const path = newPath.trim();
    if (!path) return;
    setNewPath('');
    await props.onAdd(path);
  };

  return (
    <section className="context-source-directories">
      <header className="context-source-directories-head">
        <span><Icon name="folder" size={12} /> Directorios fuente</span>
        <small>{props.directories.length} vinculados</small>
      </header>

      <form
        className="context-source-directories-form"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAdd();
        }}
      >
        <input
          value={newPath}
          onChange={(event) => setNewPath(event.target.value)}
          placeholder="Ruta del directorio (ej. workspace/.bago/docs)"
          aria-label="Ruta del directorio a vincular"
        />
        <button type="submit" disabled={!newPath.trim()}>
          <Icon name="plus" size={11} /> Vincular directorio
        </button>
      </form>

      {props.directories.length === 0 ? (
        <p className="context-source-directories-empty">
          Sin directorios vinculados. Añade una ruta para ver sus archivos.
        </p>
      ) : (
        <ul className="context-source-directories-list">
          {props.directories.map((dir) => {
            const isExpanded = expandedId === dir.id;
            const linked = dir.files.filter((f) => f.include).length;
            return (
              <li key={dir.id} className={`context-source-directory ${isExpanded ? 'is-expanded' : ''}`}>
                <header className="context-source-directory-head">
                  <button
                    type="button"
                    className="context-source-directory-toggle"
                    onClick={() => setExpandedId(isExpanded ? null : dir.id)}
                    aria-expanded={isExpanded}
                  >
                    <Icon name="chevron" size={11} />
                  </button>
                  <span className="context-source-directory-name">
                    <Icon name="folder" size={12} />
                    <strong>{dir.title}</strong>
                    <code title={dir.path}>{dir.path}</code>
                  </span>
                  <small>{linked}/{dir.files.length} activos</small>
                  <div className="context-source-directory-actions">
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => void props.onRefreshFiles(dir.id)}
                      disabled={props.loading}
                      title="Releer archivos del directorio"
                    >
                      <Icon name="refresh" size={11} /> Releer
                    </button>
                    <button
                      type="button"
                      className="text-button is-primary"
                      onClick={async () => {
                        if (linkingId) return;
                        setLinkingId(dir.id);
                        try {
                          await props.onLinkToTree(dir.id);
                        } finally {
                          setLinkingId(null);
                        }
                      }}
                      disabled={linkingId !== null || linked === 0}
                      title="Crear nodos en el árbol para los archivos activos"
                    >
                      <Icon name="tree" size={11} /> {linkingId === dir.id ? 'Vinculando…' : 'Vincular al árbol'}
                    </button>
                    <button
                      type="button"
                      className="text-button is-danger"
                      onClick={() => void props.onRemove(dir.id)}
                      title="Quitar directorio"
                    >
                      <Icon name="close" size={11} />
                    </button>
                  </div>
                </header>
                {isExpanded && (
                  <div className="context-source-directory-body">
                    {dir.files.length === 0 ? (
                      <p className="context-source-directory-empty">
                        {props.loading ? 'Cargando archivos…' : 'No se encontraron archivos en este directorio. Pulsa "Releer" para volver a intentarlo.'}
                      </p>
                    ) : (
                      <table className="context-source-files">
                        <thead>
                          <tr>
                            <th></th>
                            <th>Archivo</th>
                            <th>Rama</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dir.files.map((file) => (
                            <tr key={file.path} className={file.include ? 'is-included' : 'is-excluded'}>
                              <td>
                                <input
                                  type="checkbox"
                                  checked={file.include}
                                  onChange={(event) => void props.onToggleInclude(dir.id, file.path, event.target.checked)}
                                  aria-label={`Incluir ${file.title}`}
                                />
                              </td>
                              <td>
                                <div className="context-source-file-name">
                                  <Icon name="file" size={11} />
                                  <strong>{file.title}</strong>
                                  <code>{file.path}</code>
                                </div>
                              </td>
                              <td>
                                <select
                                  value={file.branch}
                                  onChange={(event) => void props.onSetBranch(dir.id, file.path, event.target.value as ContextNodeType)}
                                  disabled={!file.include}
                                  aria-label={`Rama de ${file.title}`}
                                >
                                  {BRANCH_LABELS.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                  ))}
                                </select>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
