import { useEffect, useState } from 'react';
import type { BagoAction } from '@/navigation/actionRegistry';
import { Icon } from '@/shared/Icon';

export function filterPaletteActions(actions: BagoAction[], query: string): BagoAction[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return actions;
  return actions.filter((item) => (
    [item.label, item.object, item.verb, item.group, ...(item.keywords || [])]
      .join(' ')
      .toLowerCase()
      .includes(needle)
  ));
}

export function ActivityToast({ message, busy, state }: { message: string; busy: boolean; state: string }) {
  const label = message || (busy ? 'procesando' : 'sin actividad reciente');
  return (
    <div className={`activity-toast state-${busy ? 'loading' : state}`} role="status" aria-live="polite">
      <span className="activity-toast-dot" />
      <span>{label}</span>
    </div>
  );
}

export function HelpOverlay({ onClose, onOpenFirstRun }: { onClose: () => void; onOpenFirstRun: () => void }) {
  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape' || event.key === '?') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const shortcuts = [
    ['Ctrl K', 'Abrir comandos y búsqueda'],
    ['Ctrl B', 'Mostrar u ocultar navegación'],
    ['Ctrl Shift C', 'Acoplar o desacoplar el chat a la pantalla actual'],
    ['?', 'Abrir esta ayuda'],
    ['Esc', 'Cerrar modales, ayuda o paleta'],
    ['Enter', 'Enviar chat cuando el cursor está en el composer'],
    ['Shift Enter', 'Nueva línea en el composer']
  ];

  return (
    <div className="command-palette-backdrop help-backdrop" role="dialog" aria-modal="true" aria-label="Atajos de teclado">
      <div className="help-panel">
        <header>
          <div><span className="surface-eyebrow">Ayuda rápida</span><h2>Atajos y modelo de navegación</h2></div>
          <button className="icon-button" type="button" onClick={onClose} title="Cerrar ayuda"><Icon name="close" /></button>
        </header>
        <section className="help-grid">
          {shortcuts.map(([key, description]) => <div key={key} className="help-shortcut-row"><kbd>{key}</kbd><span>{description}</span></div>)}
        </section>
        <button type="button" className="secondary-button" onClick={onOpenFirstRun}>Abrir recorrido inicial</button>
        <p className="help-note">El sidebar contiene destinos. El chat puede usarse como pantalla completa (Ctrl+2) o acoplarse junto a cualquier otra pantalla (botón de cabecera o Ctrl+Shift+C). Los paneles laterales del sidebar (agentes, intérprete, GitHub, capacidades, herramientas) nunca comparten el área de trabajo: al abrirse ocupan toda la pantalla. Solo el chat acoplado puede dividir la vista.</p>
      </div>
    </div>
  );
}

export function CommandPalette({ actions, onClose }: { actions: BagoAction[]; onClose: () => void }) {
  const [query, setQuery] = useState('');
  const filtered = filterPaletteActions(actions, query);

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="command-palette-backdrop" role="dialog" aria-modal="true" aria-label="Comandos rápidos">
      <div className="command-palette">
        <div className="command-palette-search">
          <span>/</span>
          <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar módulo, acción o comando" />
          <kbd>Esc</kbd>
        </div>
        <div className="command-palette-list">
          {filtered.length ? filtered.map((item) => (
            <button key={item.id} type="button" onClick={() => { item.action(); onClose(); }}>
              <span className="palette-item-main"><Icon name={item.icon} size={14} /><span><strong>{item.label}</strong><small>{item.group}</small></span></span>
              <kbd>{item.shortcut || '↵'}</kbd>
            </button>
          )) : <div className="palette-empty">No hay acciones que coincidan.</div>}
        </div>
      </div>
    </div>
  );
}
