// src/features/workspace/workspaceTypes.ts
// Tipos para el módulo de editor de Workspace.

import type { SelectionRecord } from '@/contracts/backend';

export type Language =
  | 'typescript'
  | 'tsx'
  | 'javascript'
  | 'jsx'
  | 'python'
  | 'json'
  | 'markdown'
  | 'css'
  | 'html'
  | 'shell'
  | 'yaml'
  | 'toml'
  | 'dotenv'
  | 'text'
  | 'unknown';

export interface OpenFileTab {
  id: string;
  path: string;
  language: Language;
  /** Etiqueta corta (basename). */
  label: string;
  /** Contenido original cargado desde disco (para detectar dirty). */
  baseline: string;
  /** Contenido actual del editor. */
  content: string;
  state: 'clean' | 'dirty' | 'saving' | 'saved' | 'save_error' | 'readonly';
  /** Si está en el árbol de contexto. */
  inContext: boolean;
  /** Si tiene evidencia asociada. */
  withEvidence: boolean;
  /** Diagnostics del archivo. */
  diagnostics: WorkspaceDiagnostic[];
  /** Patrones detectados. */
  patterns: WorkspacePattern[];
  /** Última vez que se cargó desde disco. */
  loadedAt?: string;
  /** Hash/hash del último load para detectar cambios en disco. */
  baselineHash?: string;
}

export type DiagnosticSeverity = 'error' | 'warning' | 'info' | 'hint';

export interface WorkspaceDiagnostic {
  id: string;
  path: string;
  severity: DiagnosticSeverity;
  startLine: number;
  endLine: number;
  startColumn: number;
  endColumn: number;
  message: string;
  source: string;
  code?: string;
  origin: 'local' | 'backend';
}

export type PatternCategory =
  | 'code'
  | 'ui'
  | 'bago'
  | 'security';

export interface WorkspacePattern {
  id: string;
  path: string;
  category: PatternCategory;
  kind: string;
  title: string;
  detail: string;
  startLine: number;
  endLine: number;
  startColumn: number;
  endColumn: number;
  severity: 'low' | 'medium' | 'high';
  suggestion?: string;
}

export type WorkspaceFilter =
  | 'all'
  | 'code'
  | 'python'
  | 'typescript'
  | 'javascript'
  | 'json'
  | 'markdown'
  | 'shell'
  | 'web'
  | 'text'
  | 'directory'
  | 'with-errors';

export type BottomPanel = 'problems' | 'changes' | 'patterns' | 'output' | null;

export interface InspectorState {
  kind: 'file' | 'diagnostic' | 'pattern' | null;
  refId?: string;
}

export interface SelectedRange {
  path: string;
  startLine: number;
  endLine: number;
  startColumn: number;
  endColumn: number;
  text: string;
}

export interface OutputEntry {
  id: string;
  ts: string;
  channel: 'lint' | 'typecheck' | 'save' | 'analyze' | 'command' | 'info';
  text: string;
  level: 'info' | 'ok' | 'error' | 'warn';
}

export interface WorkspaceEditorState {
  files: Array<Record<string, unknown>>;
  openTabs: OpenFileTab[];
  activePath: string | null;
  filter: WorkspaceFilter;
  query: string;
  inspector: InspectorState;
  bottomPanel: BottomPanel;
  inspectorOpen: boolean;
  saving: boolean;
  expandedDirectories: string[];
  error?: string;
}

export type WorkspaceFileKind = 'directory' | 'code' | 'file';

export interface ExplorerNode {
  path: string;
  name: string;
  kind: WorkspaceFileKind;
  language: Language;
  children: ExplorerNode[];
  size?: number;
  modified?: string;
  extension?: string;
}

export interface WorkspaceFileRef {
  path: string;
  content: string;
  raw?: unknown;
}

export type InspectorContextSelection = SelectionRecord;
