import { useEffect, type MouseEvent as ReactMouseEvent } from 'react';
import type { InspectorLevel, SelectionRecord } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';

interface InspectorDrawerProps {
  selection: SelectionRecord;
  level: InspectorLevel;
  onClose: () => void;
  onOpenContextMenu: (selection: SelectionRecord, position: { x: number; y: number }) => void;
}

function rawText(selection: SelectionRecord): string {
  return JSON.stringify(selection.raw ?? {}, null, 2) || '';
}

export function InspectorDrawer({ selection, level, onClose, onOpenContextMenu }: InspectorDrawerProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const openActions = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    onOpenContextMenu(selection, { x: rect.left, y: rect.bottom + 6 });
  };

  const showRaw = level === 'raw';

  return (
    <aside className="inspector-drawer" role="dialog" aria-modal="false" aria-label={`Inspector de ${selection.title}`}>
      <header className="inspector-drawer-header">
        <div>
          <span className="inspector-drawer-kind">{selection.kind}</span>
          <h3>{selection.title}</h3>
        </div>
        <div className="inspector-drawer-actions">
          <button type="button" className="icon-button" title="Acciones" onClick={openActions}>
            <Icon name="more" size={15} />
          </button>
          <button type="button" className="icon-button" title="Cerrar inspector" onClick={onClose}>
            <Icon name="close" size={15} />
          </button>
        </div>
      </header>

      <section className="inspector-drawer-body">
        <div className="inspector-drawer-summary">
          <span>Nivel: {level}</span>
          <p>{selection.summary || 'Sin resumen disponible.'}</p>
        </div>

        {selection.detail.length > 0 && (
          <dl className="inspector-detail-list">
            {selection.detail.map((entry, index) => {
              const [key, ...rest] = entry.split(':');
              return (
                <div key={`${entry}-${index}`}>
                  <dt>{rest.length ? key.trim() : `Dato ${index + 1}`}</dt>
                  <dd>{rest.length ? rest.join(':').trim() : entry}</dd>
                </div>
              );
            })}
          </dl>
        )}

        {showRaw && (
          <pre className="inspector-raw">{rawText(selection)}</pre>
        )}
      </section>
    </aside>
  );
}
