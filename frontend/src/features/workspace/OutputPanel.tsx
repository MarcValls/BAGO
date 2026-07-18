// src/features/workspace/OutputPanel.tsx
// Logs de salida (lint, typecheck, guardado, comandos).

import type { OutputEntry } from './workspaceTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  entries: OutputEntry[];
  onClear: () => void;
}

export function OutputPanel(props: Props) {
  if (props.entries.length === 0) {
    return <div className="workspace-panel-empty">Sin salida todavía.</div>;
  }
  return (
    <div className="workspace-output">
      <header className="workspace-panel-summary">
        <span><Icon name="live" size={11} /> {props.entries.length} entradas</span>
        <button type="button" className="workspace-output-clear" onClick={props.onClear}>Limpiar</button>
      </header>
      <ol className="workspace-output-list">
        {props.entries.slice(-200).map((entry) => (
          <li key={entry.id} className={`workspace-output-entry level-${entry.level} channel-${entry.channel}`}>
            <span className="workspace-output-time">{new Date(entry.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            <span className="workspace-output-channel">[{entry.channel}]</span>
            <span className="workspace-output-text">{entry.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
