// Modal de previsualización y edición de un patch. Permite al usuario
// modificar las operaciones antes de aplicarlas. Se muestra cuando el
// chat emite un patch y el usuario hace click en "Editar" o cuando se
// modifica un patch fallido.
import { useEffect, useState } from 'react';
import type { ContextPatchOp, ContextPatchRequest } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  patch: ContextPatchRequest;
  onCancel: () => void;
  onApply: (operations: ContextPatchOp[]) => void;
}

function opSummary(op: ContextPatchOp): string {
  switch (op.op) {
    case 'create': return `crear "${op.title}" en ${op.parentId}`;
    case 'move': return `mover ${op.nodeId} → ${op.newParentId}`;
    case 'update': return `editar ${op.nodeId} (${Object.keys(op.patch).join(', ')})`;
    case 'exclude': return `excluir ${op.nodeId}`;
    case 'restore': return `restaurar ${op.nodeId}`;
    case 'canon': return `${op.value ? 'marcar CANON' : 'quitar CANON'} ${op.nodeId}`;
    case 'link': return `vincular ${op.nodeId} ↔ ${op.targetId} (${op.relation})`;
    case 'unlink': return `desvincular ${op.nodeId} ↔ ${op.targetId}`;
    case 'add_to_pack': return `añadir ${op.nodeId} al pack ${op.packId}`;
    case 'remove_from_pack': return `quitar ${op.nodeId} del pack ${op.packId}`;
    default: return op.op;
  }
}

function operationAsText(op: ContextPatchOp): string {
  return JSON.stringify(op, null, 2);
}

function parseOperation(text: string): ContextPatchOp | null {
  try {
    const value = JSON.parse(text);
    if (value && typeof value === 'object' && typeof (value as { op?: unknown }).op === 'string') {
      return value as ContextPatchOp;
    }
  } catch {
    return null;
  }
  return null;
}

export function ContextPatchPreview(props: Props) {
  const [drafts, setDrafts] = useState<string[]>(props.patch.patch.operations.map(operationAsText));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDrafts(props.patch.patch.operations.map(operationAsText));
  }, [props.patch.id]);

  const update = (index: number, value: string) => {
    setDrafts((current) => current.map((entry, idx) => idx === index ? value : entry));
  };

  const apply = () => {
    const operations: ContextPatchOp[] = [];
    for (const text of drafts) {
      const op = parseOperation(text);
      if (!op) {
        setError('Una de las operaciones no es JSON válido.');
        return;
      }
      operations.push(op);
    }
    setError(null);
    props.onApply(operations);
  };

  return (
    <div className="context-patch-preview" role="dialog" aria-modal="true" aria-label="Editar patch">
      <header className="context-patch-preview-header">
        <h3><Icon name="inspector" size={14} /> Editar patch: {props.patch.title}</h3>
        <button type="button" className="icon-button" onClick={props.onCancel} aria-label="Cerrar">
          <Icon name="close" size={14} />
        </button>
      </header>
      <p className="context-patch-preview-hint">
        Edita las operaciones como JSON. El sistema validará cada cambio antes de aplicarlo.
        Nodos CANON no se editan en sitio: si necesitas modificarlos, crea una nueva versión.
      </p>
      <ol className="context-patch-preview-list">
        {drafts.map((draft, idx) => {
          const parsed = parseOperation(draft);
          return (
            <li key={idx}>
              <header>
                <span>{parsed ? opSummary(parsed) : 'JSON inválido'}</span>
                <button type="button" className="text-button" onClick={() => update(idx, '')} disabled={idx === 0}>
                  <Icon name="close" size={11} /> vaciar
                </button>
              </header>
              <textarea
                value={draft}
                onChange={(event) => update(idx, event.target.value)}
                rows={5}
                spellCheck={false}
                aria-label={`Operación ${idx + 1}`}
              />
            </li>
          );
        })}
      </ol>
      {error && <p className="context-patch-preview-error">{error}</p>}
      <footer className="context-patch-preview-actions">
        <button type="button" className="secondary-button" onClick={props.onCancel}>
          <Icon name="close" size={12} /> Cancelar
        </button>
        <button type="button" className="primary-button" onClick={apply}>
          <Icon name="check" size={12} /> Aplicar patch
        </button>
      </footer>
    </div>
  );
}
