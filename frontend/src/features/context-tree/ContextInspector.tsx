// Inspector contextual derecho. Muestra el detalle de un nodo
// seleccionado con secciones colapsables: Resumen, Origen, Relaciones,
// Peso, Evidencia, Historial. Edición por draft + botón Guardar.
import { useEffect, useState } from 'react';
import type { ContextNode, ContextNodeType } from './contextTreeTypes';
import { Icon, type IconName } from '@/shared/Icon';
import { shortenPath, formatRelativeTime, summarizeText } from './utils';

interface Props {
  node: ContextNode | null;
  relatedNodes: ContextNode[];
  treeName?: string;
  packName?: string;
  packStatus?: 'draft' | 'valid' | 'warning' | 'blocked' | 'compiled' | null;
  packNodeCount?: number;
  packConflicts?: number;
  onChange: (patch: Partial<ContextNode>) => void;
  onSave: (patch: Partial<ContextNode>) => void;
  onSelectRelated: (nodeId: string) => void;
  onOpenInWorkspace?: (path: string) => void;
  onCreatePlan?: (summary: string) => void;
  onOpenInChat?: (text: string) => void;
  onCreateTree?: () => void;
  onCompilePack?: () => void;
  hideIdentity?: boolean;
  hideTitle?: boolean;
}

function typeIcon(type: ContextNodeType): IconName {
  switch (type) {
    case 'intent': return 'intent';
    case 'source': return 'folder';
    case 'file': return 'file';
    case 'decision': return 'decision';
    case 'rule': return 'rule';
    case 'claim': return 'claim';
    case 'risk': return 'risk';
    case 'pending': return 'stale';
    case 'evidence': return 'evidence';
    case 'proposal': return 'proposed';
    case 'pack': return 'pack';
    case 'note': return 'node';
    default: return 'node';
  }
}

function typeLabel(type: ContextNodeType): string {
  switch (type) {
    case 'root': return 'Raíz';
    case 'intent': return 'Intención';
    case 'source': return 'Fuente';
    case 'file': return 'Archivo';
    case 'decision': return 'Decisión';
    case 'rule': return 'Regla';
    case 'claim': return 'Claim';
    case 'risk': return 'Riesgo';
    case 'pending': return 'Pendiente';
    case 'evidence': return 'Evidencia';
    case 'proposal': return 'Propuesta';
    case 'pack': return 'Pack';
    case 'note': return 'Nota';
    default: return type;
  }
}

function primaryActionFor(node: ContextNode): { id: string; label: string; icon: IconName; tone: 'primary' | 'normal' | 'danger' } {
  if (node.status === 'canon') return { id: 'review', label: 'Solicitar revisión', icon: 'lock', tone: 'normal' };
  if (node.status === 'proposed') return { id: 'accept', label: 'Aceptar propuesta', icon: 'check', tone: 'primary' };
  if (node.status === 'conflict') return { id: 'resolve', label: 'Resolver conflicto', icon: 'conflict', tone: 'primary' };
  if (node.status === 'stale') return { id: 'releer', label: 'Releer fuente', icon: 'refresh', tone: 'normal' };
  return { id: 'update', label: 'Actualizar', icon: 'check', tone: 'primary' };
}

export function ContextInspector(props: Props) {
  const { node } = props;
  const [summaryDraft, setSummaryDraft] = useState('');
  const [bodyDraft, setBodyDraft] = useState('');
  const [titleDraft, setTitleDraft] = useState('');
  const [priorityDraft, setPriorityDraft] = useState<ContextNode['priority']>('medium');
  const [tagsDraft, setTagsDraft] = useState('');
  const [openSection, setOpenSection] = useState<'summary' | 'relations' | 'weight'>('summary');
  const [dirty, setDirty] = useState(false);
  const packNodeCount = props.packNodeCount ?? 0;
  const packIsCompiled = props.packStatus === 'compiled' || props.packStatus === 'valid';
  const packIsEmpty = packNodeCount === 0;

  useEffect(() => {
    if (node) {
      setSummaryDraft(node.summary);
      setBodyDraft(node.body || '');
      setTitleDraft(node.title);
      setPriorityDraft(node.priority);
      setTagsDraft(node.tags.join(', '));
      setDirty(false);
    }
  }, [node?.id]);

  if (!node) {
    return (
      <aside className="context-inspector empty" aria-label="Inspector contextual">
        <header className="context-inspector-head">
          <strong>Inspector</strong>
        </header>
        <div className="context-inspector-overview">
          <h4>Cómo funciona</h4>
          {packIsCompiled && packIsEmpty ? (
            <div className="context-inspector-callout">
              <Icon name="warning" size={12} />
              <p>El pack está compilado pero vacío. Añade piezas desde Banco para poder enviarlo.</p>
            </div>
          ) : (
            <ol className="context-inspector-flow">
              <li><Icon name="folder" size={11} /> <span>Vincular fuentes</span></li>
              <li><Icon name="tree" size={11} /> <span>Organizar árbol</span></li>
              <li><Icon name="pack" size={11} /> <span>Marcar piezas del pack</span></li>
              <li><Icon name="refresh" size={11} /> <span>Compilar</span></li>
              <li><Icon name="send" size={11} /> <span>Enviar a Chat o Pipeline</span></li>
            </ol>
          )}
        </div>
        <div className="context-inspector-overview">
          <h4>Estado actual</h4>
          <ul className="context-inspector-stats">
            <li><span>Árbol</span><strong>{props.treeName || '—'}</strong></li>
            <li><span>Pack</span><strong>{props.packName || '—'}</strong></li>
            {props.packStatus && (
              <li><span>Estado</span><strong className={`state-${props.packStatus}`}>{props.packStatus}</strong></li>
            )}
            {typeof props.packNodeCount === 'number' && (
              <li><span>Piezas seleccionadas</span><strong>{props.packNodeCount}</strong></li>
            )}
            {typeof props.packConflicts === 'number' && props.packConflicts > 0 && (
              <li><span>Conflictos</span><strong className="is-warn">{props.packConflicts}</strong></li>
            )}
          </ul>
          {packIsCompiled && packIsEmpty && (
            <p className="context-inspector-empty-row">Compilado sin piezas seleccionadas: el árbol tiene categorías, pero el pack no contiene contenido.</p>
          )}
        </div>
        {!props.treeName && props.onCreateTree && (
          <button type="button" className="primary-button compact" onClick={props.onCreateTree}>
            <Icon name="plus" size={12} /> Crear árbol inicial
          </button>
        )}
        {props.treeName && props.packStatus !== 'compiled' && props.packStatus !== 'valid' && props.onCompilePack && (
          <button type="button" className="primary-button compact" onClick={props.onCompilePack}>
            <Icon name="refresh" size={12} /> Compilar pack
          </button>
        )}
      </aside>
    );
  }

  const isCanon = node.status === 'canon';
  const isEditable = !isCanon && node.type !== 'root';
  const primary = primaryActionFor(node);
  const related = props.relatedNodes.filter((n) => n.id !== node.id);
  const parent = node.parentId ? related.find((n) => n.id === node.parentId) || null : null;
  const children = related.filter((n) => n.parentId === node.id);
  const linked = related.filter((n) => node.linkedNodeIds.includes(n.id));
  const conflicts = related.filter((n) => node.conflictNodeIds.includes(n.id));

  const toggleSection = (section: typeof openSection) => {
    setOpenSection((current) => current === section ? current : section);
  };

  return (
    <aside className="context-inspector" aria-label={`Inspector de ${node.title}`}>
      <header className="context-inspector-header">
        {!props.hideIdentity && <>
          <span className="context-inspector-icon"><Icon name={typeIcon(node.type)} size={14} /></span>
          <div className="context-inspector-meta">
            <small>{typeLabel(node.type)}</small>
            <strong title={node.title}>{node.title}</strong>
            <span className="context-inspector-status-row">
              {node.status !== 'active' && (
                <span className={`context-inspector-status is-${node.status}`}>{node.status}</span>
              )}
              {node.conflictNodeIds.length > 0 && (
                <span className="context-inspector-status is-conflict">
                  <Icon name="conflict" size={10} /> {node.conflictNodeIds.length} conflicto{node.conflictNodeIds.length > 1 ? 's' : ''}
                </span>
              )}
              {typeof node.weightTokens === 'number' && node.weightTokens > 0 && (
                <span className="context-inspector-weight">{node.weightTokens}t</span>
              )}
            </span>
          </div>
        </>}
        <button
          type="button"
          className={`primary-button compact context-inspector-primary`}
          onClick={() => {
            if (dirty) {
              const tags = tagsDraft.split(',').map((t) => t.trim()).filter(Boolean);
              props.onSave({
                title: titleDraft,
                summary: summaryDraft,
                body: bodyDraft,
                priority: priorityDraft,
                tags
              });
            } else {
              const patch: Partial<ContextNode> = {};
              if (node.status === 'proposed') patch.status = 'active';
              if (node.status === 'conflict') patch.status = 'active';
              if (node.status === 'stale') patch.status = 'active';
              props.onSave(patch);
            }
          }}
        >
          <Icon name={primary.icon} size={12} /> {primary.label}
        </button>
      </header>

      <nav className="context-inspector-tabs" role="tablist">
        <button type="button" className={openSection === 'summary' ? 'is-active' : ''} onClick={() => toggleSection('summary')}>Resumen</button>
        <button type="button" className={openSection === 'relations' ? 'is-active' : ''} onClick={() => toggleSection('relations')}>Relaciones</button>
        <button type="button" className={openSection === 'weight' ? 'is-active' : ''} onClick={() => toggleSection('weight')}>Detalle</button>
      </nav>

      {openSection === 'summary' && (
        <section className="context-inspector-section">
          {!props.hideTitle && <label>
            <small>Título</small>
            <input
              value={titleDraft}
              onChange={(event) => { setTitleDraft(event.target.value); setDirty(true); }}
              disabled={!isEditable}
              aria-label="Título del nodo"
            />
          </label>}
          <label>
            <small>Resumen</small>
            <textarea
              value={summaryDraft}
              onChange={(event) => { setSummaryDraft(event.target.value); setDirty(true); }}
              disabled={!isEditable}
              rows={3}
              aria-label="Resumen del nodo"
              placeholder="Una frase que explique qué representa este nodo."
            />
          </label>
          <label>
            <small>Cuerpo</small>
            <textarea
              value={bodyDraft}
              onChange={(event) => { setBodyDraft(event.target.value); setDirty(true); }}
              disabled={!isEditable}
              rows={5}
              aria-label="Cuerpo del nodo"
              placeholder="Detalle, evidencia inline o instrucciones para el modelo."
            />
          </label>
          <div className="context-inspector-row">
            <label>
              <small>Prioridad</small>
              <select
                value={priorityDraft}
                onChange={(event) => { setPriorityDraft(event.target.value as ContextNode['priority']); setDirty(true); }}
                disabled={!isEditable}
                aria-label="Prioridad"
              >
                <option value="low">Baja</option>
                <option value="medium">Media</option>
                <option value="high">Alta</option>
                <option value="critical">Crítica</option>
              </select>
            </label>
            <label>
              <small>Tags (coma)</small>
              <input
                value={tagsDraft}
                onChange={(event) => { setTagsDraft(event.target.value); setDirty(true); }}
                disabled={!isEditable}
                aria-label="Tags"
              />
            </label>
          </div>
          <div className="context-inspector-actions">
            <button
              type="button"
              className="primary-button compact"
              disabled={!isEditable || !dirty}
              onClick={() => {
                const tags = tagsDraft.split(',').map((t) => t.trim()).filter(Boolean);
                props.onSave({ title: titleDraft, summary: summaryDraft, body: bodyDraft, priority: priorityDraft, tags });
                setDirty(false);
              }}
            >
              <Icon name="check" size={12} /> Guardar cambios
            </button>
            {isCanon && (
              <span className="context-inspector-hint">
                <Icon name="lock" size={12} /> CANON no se edita en sitio. Crea una nueva versión o una contradicción.
              </span>
            )}
            <button
              type="button"
              className="text-button"
              onClick={() => props.onOpenInChat?.(`Nodo ${node.id} · ${node.title}\n\n${node.summary}\n\n${node.body || ''}`)}
            >
              <Icon name="send" size={12} /> Enviar al chat
            </button>
            {(node.type === 'risk' || node.type === 'pending' || node.type === 'proposal' || node.type === 'decision') && props.onCreatePlan && (
              <button
                type="button"
                className="text-button"
                onClick={() => props.onCreatePlan?.(`Resolver nodo de contexto: ${node.title}\n\n${node.summary}`)}
              >
                <Icon name="pipeline" size={12} /> Crear tarea en pipeline
              </button>
            )}
          </div>
        </section>
      )}

      {openSection === 'relations' && (
        <section className="context-inspector-section">
          <h4>Padre</h4>
          {parent ? (
            <button type="button" className="context-inspector-related" onClick={() => props.onSelectRelated(parent.id)}>
              <Icon name={typeIcon(parent.type)} size={12} /> {parent.title}
            </button>
          ) : <p className="context-inspector-empty-row">Sin padre (raíz).</p>}
          <h4>Hijos ({children.length})</h4>
          {children.length === 0 ? (
            <p className="context-inspector-empty-row">Sin hijos directos.</p>
          ) : (
            <ul className="context-inspector-related-list">
              {children.map((child) => (
                <li key={child.id}>
                  <button type="button" onClick={() => props.onSelectRelated(child.id)}>
                    <Icon name={typeIcon(child.type)} size={11} /> {summarizeText(child.title, 60)}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h4>Vínculos laterales</h4>
          {linked.length === 0 ? <p className="context-inspector-empty-row">Sin vínculos laterales.</p> : (
            <ul className="context-inspector-related-list">
              {linked.map((entry) => (
                <li key={entry.id}>
                  <button type="button" onClick={() => props.onSelectRelated(entry.id)}>
                    <Icon name="link" size={11} /> {summarizeText(entry.title, 60)}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h4>Conflictos</h4>
          {conflicts.length === 0 ? <p className="context-inspector-empty-row">Sin conflictos abiertos.</p> : (
            <ul className="context-inspector-related-list">
              {conflicts.map((entry) => (
                <li key={entry.id}>
                  <button type="button" onClick={() => props.onSelectRelated(entry.id)}>
                    <Icon name="conflict" size={11} /> {summarizeText(entry.title, 60)}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {openSection === 'weight' && (
        <section className="context-inspector-section">
          <h4>Origen</h4>
          {node.sourceRefs.length === 0 ? (
            <p className="context-inspector-empty-row">Sin origen registrado.</p>
          ) : (
            <ul className="context-inspector-refs">
              {node.sourceRefs.map((ref, idx) => (
                <li key={idx}>
                  <strong>{ref.kind}</strong>
                  {ref.path ? <code title={ref.path}>{shortenPath(ref.path, 60)}</code> : null}
                  {ref.path && props.onOpenInWorkspace && (
                    <button type="button" className="text-button" onClick={() => props.onOpenInWorkspace?.(ref.path || '')}>
                      <Icon name="workspace" size={10} /> Abrir
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          <h4>Evidencia vinculada</h4>
          {node.evidenceRefs.length === 0 ? (
            <p className="context-inspector-empty-row">Sin evidencia asociada.</p>
          ) : (
            <ul className="context-inspector-refs">
              {node.evidenceRefs.map((ref) => (
                <li key={ref}><code>{ref}</code></li>
              ))}
            </ul>
          )}
          <h4>Historial</h4>
          <p className="context-inspector-history-row">
            Creado por <strong>{node.createdBy}</strong> · {formatRelativeTime(node.createdAt)}<br />
            Actualizado por <strong>{node.updatedBy}</strong> · {formatRelativeTime(node.updatedAt)}
          </p>
          {props.relatedNodes.length > 0 && (
            <details className="context-inspector-receipts">
              <summary>Piezas relacionadas ({props.relatedNodes.length})</summary>
              <ul>
                {props.relatedNodes.slice(0, 6).map((entry) => (
                  <li key={entry.id}><code>{entry.id.slice(0, 12)}</code> {entry.title}</li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

    </aside>
  );
}
