// src/features/workspace/WorkspaceInspector.tsx
// Inspector lateral contextual. Tres modos: archivo, diagnóstico, patrón.

import type {
  OpenFileTab,
  WorkspaceDiagnostic,
  WorkspacePattern
} from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  tab: OpenFileTab | null;
  inspector: { kind: 'file' | 'diagnostic' | 'pattern' | null; refId?: string };
  diagnostic: WorkspaceDiagnostic | null;
  pattern: WorkspacePattern | null;
  onClose: () => void;
  onSendToChat: () => void;
  onAddToContext: () => void;
  onCreatePlan: () => void;
  onCopyPath: () => void;
  onViewEvidence: () => void;
  onJump: (line: number) => void;
}

export function WorkspaceInspector(props: Props) {
  const { tab } = props;
  if (!tab) {
    return (
      <div className="workspace-inspector empty">
        <header className="workspace-inspector-head">
          <strong>Inspector</strong>
        </header>
        <p className="workspace-inspector-empty">Selecciona un archivo o problema para ver su detalle.</p>
      </div>
    );
  }
  return (
    <aside className="workspace-inspector">
      <header className="workspace-inspector-head">
        <strong>Inspector</strong>
        <button type="button" className="workspace-inspector-close" onClick={props.onClose} aria-label="Cerrar inspector">
          <Icon name="close" size={12} />
        </button>
      </header>
      {props.inspector.kind === 'diagnostic' && props.diagnostic && (
        <DiagnosticInspector
          tab={tab}
          diagnostic={props.diagnostic}
          onJump={props.onJump}
          onSendToChat={props.onSendToChat}
          onAddToContext={props.onAddToContext}
          onCreatePlan={props.onCreatePlan}
        />
      )}
      {props.inspector.kind === 'pattern' && props.pattern && (
        <PatternInspector
          tab={tab}
          pattern={props.pattern}
          onJump={props.onJump}
          onSendToChat={props.onSendToChat}
          onAddToContext={props.onAddToContext}
          onCreatePlan={props.onCreatePlan}
        />
      )}
      {(props.inspector.kind === 'file' || !props.inspector.kind) && (
        <FileInspector
          tab={tab}
          onSendToChat={props.onSendToChat}
          onAddToContext={props.onAddToContext}
          onCreatePlan={props.onCreatePlan}
          onCopyPath={props.onCopyPath}
          onViewEvidence={props.onViewEvidence}
          onJump={props.onJump}
        />
      )}
    </aside>
  );
}

function FileInspector(p: {
  tab: OpenFileTab;
  onSendToChat: () => void;
  onAddToContext: () => void;
  onCreatePlan: () => void;
  onCopyPath: () => void;
  onViewEvidence: () => void;
  onJump: (line: number) => void;
}) {
  return (
    <div className="workspace-inspector-body">
      <div className="workspace-inspector-section">
        <span className="workspace-inspector-label">Ruta</span>
        <code className="workspace-inspector-path" title={p.tab.path}>{p.tab.path}</code>
      </div>
      <div className="workspace-inspector-grid">
        <div><span>Lenguaje</span><strong>{p.tab.language}</strong></div>
        <div><span>Estado</span><strong className={`state-${p.tab.state}`}>{p.tab.state}</strong></div>
        <div><span>Tamaño</span><strong>{p.tab.content.length} chars</strong></div>
        <div><span>En contexto</span><strong>{p.tab.inContext ? 'sí' : 'no'}</strong></div>
        <div><span>Con evidencia</span><strong>{p.tab.withEvidence ? 'sí' : 'no'}</strong></div>
        <div><span>Cargado</span><strong>{p.tab.loadedAt ? new Date(p.tab.loadedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</strong></div>
      </div>
      <div className="workspace-inspector-actions">
        <button type="button" onClick={p.onAddToContext}><Icon name="tree" size={12} /> Añadir al Árbol de Contexto</button>
        <button type="button" onClick={p.onSendToChat}><Icon name="send" size={12} /> Enviar al Chat</button>
        <button type="button" onClick={p.onCreatePlan}><Icon name="pipeline" size={12} /> Crear tarea</button>
        <button type="button" onClick={p.onViewEvidence}><Icon name="evidence" size={12} /> Ver evidencia</button>
        <button type="button" onClick={p.onCopyPath}><Icon name="copy" size={12} /> Copiar ruta</button>
      </div>
      <div className="workspace-inspector-section">
        <span className="workspace-inspector-label">Diagnósticos</span>
        {p.tab.diagnostics.length === 0 ? (
          <p className="workspace-inspector-muted">Sin diagnósticos activos.</p>
        ) : (
          <ul className="workspace-inspector-list">
            {p.tab.diagnostics.map((d) => (
              <li key={d.id} className={`severity-${d.severity}`}>
                <button type="button" onClick={() => p.onJump(d.startLine)}>
                  {d.severity} {d.startLine}:{d.startColumn} — {d.message}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="workspace-inspector-section">
        <span className="workspace-inspector-label">Patrones</span>
        {p.tab.patterns.length === 0 ? (
          <p className="workspace-inspector-muted">Sin patrones relevantes.</p>
        ) : (
          <ul className="workspace-inspector-list">
            {p.tab.patterns.map((pat) => (
              <li key={pat.id}>
                <button type="button" onClick={() => p.onJump(pat.startLine)}>
                  {pat.title} <span className="workspace-inspector-line">L{pat.startLine}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function DiagnosticInspector(p: {
  tab: OpenFileTab;
  diagnostic: WorkspaceDiagnostic;
  onJump: (line: number) => void;
  onSendToChat: () => void;
  onAddToContext: () => void;
  onCreatePlan: () => void;
}) {
  return (
    <div className="workspace-inspector-body">
      <div className="workspace-inspector-section">
        <span className={`workspace-inspector-badge severity-${p.diagnostic.severity}`}>{p.diagnostic.severity}</span>
        <h3>{p.diagnostic.message}</h3>
      </div>
      <div className="workspace-inspector-grid">
        <div><span>Origen</span><strong>{p.diagnostic.source || p.diagnostic.origin}</strong></div>
        <div><span>Línea</span><strong>{p.diagnostic.startLine}</strong></div>
        <div><span>Columna</span><strong>{p.diagnostic.startColumn}</strong></div>
        <div><span>Archivo</span><strong>{p.tab.label}</strong></div>
        {p.diagnostic.code && <div><span>Código</span><strong>{p.diagnostic.code}</strong></div>}
      </div>
      <div className="workspace-inspector-actions">
        <button type="button" onClick={() => p.onJump(p.diagnostic.startLine)}><Icon name="arrowRight" size={12} /> Ir a línea</button>
        <button type="button" onClick={p.onSendToChat}><Icon name="send" size={12} /> Enviar al Chat</button>
        <button type="button" onClick={p.onAddToContext}><Icon name="risk" size={12} /> Añadir como riesgo</button>
        <button type="button" onClick={p.onCreatePlan}><Icon name="pipeline" size={12} /> Crear tarea</button>
      </div>
    </div>
  );
}

function PatternInspector(p: {
  tab: OpenFileTab;
  pattern: WorkspacePattern;
  onJump: (line: number) => void;
  onSendToChat: () => void;
  onAddToContext: () => void;
  onCreatePlan: () => void;
}) {
  return (
    <div className="workspace-inspector-body">
      <div className="workspace-inspector-section">
        <span className={`workspace-inspector-badge severity-${p.pattern.severity}`}>{p.pattern.severity}</span>
        <h3>{p.pattern.title}</h3>
        <p className="workspace-inspector-muted">{p.pattern.detail}</p>
      </div>
      <div className="workspace-inspector-grid">
        <div><span>Categoría</span><strong>{p.pattern.category}</strong></div>
        <div><span>Tipo</span><strong>{p.pattern.kind}</strong></div>
        <div><span>Línea</span><strong>{p.pattern.startLine}</strong></div>
        <div><span>Archivo</span><strong>{p.tab.label}</strong></div>
      </div>
      {p.pattern.suggestion && (
        <div className="workspace-inspector-section">
          <span className="workspace-inspector-label">Sugerencia</span>
          <p>{p.pattern.suggestion}</p>
        </div>
      )}
      <div className="workspace-inspector-actions">
        <button type="button" onClick={() => p.onJump(p.pattern.startLine)}><Icon name="arrowRight" size={12} /> Ir a línea</button>
        <button type="button" onClick={p.onSendToChat}><Icon name="send" size={12} /> Enviar al Chat</button>
        <button type="button" onClick={p.onAddToContext}><Icon name="risk" size={12} /> Añadir al contexto</button>
        <button type="button" onClick={p.onCreatePlan}><Icon name="pipeline" size={12} /> Crear tarea</button>
      </div>
    </div>
  );
}
