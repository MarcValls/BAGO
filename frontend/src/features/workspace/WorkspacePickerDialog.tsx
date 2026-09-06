import { useCallback, useEffect, useRef, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';
import { useProjectInspection } from './useProjectInspection';

interface BrowseSnapshot {
  path: string;
  parent: string;
  roots: Array<{ label: string; path: string }>;
  recent: Array<{ label: string; path: string }>;
  breadcrumbs: Array<{ label: string; path: string }>;
  directories: Array<{ name: string; path: string }>;
  truncated?: boolean;
}

type BrowseState = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; data: BrowseSnapshot };
interface Props {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  onChooseExplorer?: (defaultPath?: string) => Promise<string | null>;
  onConfirm: (seed: boolean) => void;
  client: BagoClient;
  mode?: 'activate' | 'select';
  title?: string;
}

export function WorkspacePickerDialog({ value, onChange, onClose, onChooseExplorer, onConfirm, client, mode = 'activate', title = 'Elegir directorio de trabajo' }: Props) {
  const initialPath = useRef(value);
  const browseRequestRef = useRef(0);
  const [browse, setBrowse] = useState<BrowseState>({ kind: 'loading' });
  const inspect = useProjectInspection(value, client);

  const openDirectory = useCallback(async (path?: string) => {
    const requestId = ++browseRequestRef.current;
    setBrowse({ kind: 'loading' });
    try {
      const data = await client.browseWorkspace(path);
      if (requestId !== browseRequestRef.current) return;
      setBrowse({ kind: 'ready', data });
      onChange(data.path);
    } catch (error) {
      if (requestId !== browseRequestRef.current) return;
      setBrowse({ kind: 'error', message: error instanceof Error ? error.message : 'No se pudo leer la carpeta' });
    }
  }, [client, onChange]);

  useEffect(() => { void openDirectory(initialPath.current); }, [openDirectory]);

  const isReady = inspect.kind === 'ready' && inspect.configured && inspect.linked && inspect.bindingConfirmed;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (
        event.key === 'Enter'
        && (event.ctrlKey || event.metaKey)
        && value.trim()
        && (mode === 'select' || inspect.kind !== 'loading')
      ) onConfirm(mode === 'activate' && !isReady);
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, [inspect.kind, isReady, mode, onClose, onConfirm, value]);

  const chooseNative = async () => {
    if (!onChooseExplorer) return;
    const selected = await onChooseExplorer(value);
    if (selected) await openDirectory(selected);
  };

  return (
    <div className="command-palette-backdrop workspace-picker-backdrop" role="dialog" aria-modal="true" aria-labelledby="workspace-picker-title">
      <section className="workspace-browser">
        <header className="workspace-browser-head">
          <div><span className="surface-eyebrow">Workspace</span><h2 id="workspace-picker-title">{title}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Cerrar"><Icon name="close" /></button>
        </header>

        <div className="workspace-browser-path">
          <Icon name="folder" size={15} />
          <input autoFocus value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.ctrlKey && !event.metaKey) void openDirectory(value); }} placeholder="Ruta completa del directorio" />
          <button className="secondary-button compact" type="button" onClick={() => void openDirectory(value)}>Ir</button>
        </div>

        {browse.kind === 'ready' && (
          <nav className="workspace-browser-crumbs" aria-label="Ruta actual">
            {browse.data.breadcrumbs.map((crumb, index) => <button type="button" key={crumb.path} onClick={() => void openDirectory(crumb.path)}>{index > 0 && <span>/</span>}{crumb.label}</button>)}
          </nav>
        )}

        <div className="workspace-browser-body">
          <aside className="workspace-browser-locations">
            <LocationGroup title="Recientes" items={browse.kind === 'ready' ? browse.data.recent : []} onOpen={openDirectory} />
            <LocationGroup title="Ubicaciones" items={browse.kind === 'ready' ? browse.data.roots : []} onOpen={openDirectory} />
          </aside>

          <section className="workspace-browser-directories" aria-label="Carpetas">
            {browse.kind === 'loading' && <div className="workspace-browser-empty"><span className="spinner" /> Leyendo carpetas…</div>}
            {browse.kind === 'error' && <div className="workspace-browser-empty is-error"><Icon name="warning" /> {browse.message}<small>Puedes pegar una ruta y continuar manualmente.</small></div>}
            {browse.kind === 'ready' && <>
              {browse.data.parent && <button type="button" className="workspace-directory-row is-parent" onClick={() => void openDirectory(browse.data.parent)}><Icon name="chevron" size={13} /><span>Subir un nivel</span></button>}
              {browse.data.directories.map((directory) => <button type="button" className="workspace-directory-row" key={directory.path} onClick={() => void openDirectory(directory.path)}><Icon name="folder" size={15} /><span>{directory.name}</span><Icon name="chevron" size={12} /></button>)}
              {!browse.data.directories.length && <div className="workspace-browser-empty">Esta carpeta no contiene subcarpetas.</div>}
              {browse.data.truncated && <small className="workspace-browser-limit">Se muestran las primeras 500 carpetas.</small>}
            </>}
          </section>

          <aside className="workspace-browser-preview">
            <span className="surface-eyebrow">Vista previa</span>
            <strong>{value.split(/[\\/]/).filter(Boolean).slice(-1)[0] || value || 'Sin seleccionar'}</strong>
            <code>{value || 'Elige una carpeta'}</code>
            {inspect.kind === 'loading' && <p>Inspeccionando…</p>}
            {inspect.kind === 'error' && <p className="is-error"><Icon name="warning" size={12} /> {inspect.message}</p>}
            {inspect.kind === 'ready' && isReady && <p className="is-ok"><Icon name="check" size={12} /> Configurado y vinculado</p>}
            {inspect.kind === 'ready' && !isReady && <p className="is-warn"><Icon name="warning" size={12} /> Requiere inicialización{inspect.bindingReason ? ` · ${inspect.bindingReason}` : ''}</p>}
          </aside>
        </div>

        <footer className="workspace-browser-actions">
          <div>{onChooseExplorer && <button type="button" className="secondary-button compact" onClick={() => void chooseNative()}><Icon name="folder" size={13} /> Abrir Explorer</button>}</div>
          <div><button type="button" className="secondary-button compact" onClick={onClose}>Cancelar</button>{mode === 'select' ? <button type="button" className="primary-button compact" disabled={!value.trim()} onClick={() => onConfirm(false)}>Usar esta carpeta</button> : isReady ? <button type="button" className="primary-button compact" onClick={() => onConfirm(false)}>Activar workspace</button> : <><button type="button" className="secondary-button compact" disabled={!value.trim() || inspect.kind === 'loading'} onClick={() => onConfirm(false)}>Activar sin sembrar</button><button type="button" className="primary-button compact" disabled={!value.trim() || inspect.kind === 'loading'} onClick={() => onConfirm(true)}>Sembrar y activar</button></>}</div>
        </footer>
      </section>
    </div>
  );
}

function LocationGroup({ title, items, onOpen }: { title: string; items: Array<{ label: string; path: string }>; onOpen: (path: string) => Promise<void> }) {
  if (!items.length) return null;
  return <section><span>{title}</span>{items.map((item) => <button type="button" key={item.path} title={item.path} onClick={() => void onOpen(item.path)}><Icon name="workspace" size={13} /><span>{item.label}</span></button>)}</section>;
}
