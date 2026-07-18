// src/features/workspace/CodeEditorPane.tsx
// Editor de código ligero: textarea transparente sobre un overlay de
// tokens resaltados. Numeración de líneas, gutter de diagnósticos y
// patrones, soporte de selección, atajos de teclado y pegado masivo.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, KeyboardEvent, MouseEvent } from 'react';
import type { OpenFileTab, SelectedRange, WorkspaceDiagnostic, WorkspacePattern } from './workspaceTypes';
import { tokenizeContent, type Token } from './highlight';

interface Props {
  tab: OpenFileTab;
  selectedRange: SelectedRange | null;
  onChange: (content: string) => void;
  onSelect: (range: SelectedRange | null) => void;
  onRunCommand: (command: string) => void;
  onRequestSave: () => void;
  onRequestDiagnostic: (diagnostic: WorkspaceDiagnostic) => void;
  onRequestPattern: (pattern: WorkspacePattern) => void;
  onContextMenu?: (event: MouseEvent<HTMLDivElement>, range: SelectedRange | null) => void;
}

interface MarkerEntry {
  line: number;
  severity: 'error' | 'warning' | 'info' | 'hint' | 'pattern';
  patternId?: string;
  diagnosticId?: string;
  patternKind?: string;
  patternSeverity?: 'low' | 'medium' | 'high';
}

const LINE_HEIGHT = 19; // px.
const CHARS_PER_INDENT = 2;
const FONT_SIZE = 13;

function padLine(n: number, max: number): string {
  const width = String(max).length;
  return String(n).padStart(width, ' ');
}

function gutterForTab(tab: OpenFileTab): MarkerEntry[] {
  const markers: MarkerEntry[] = [];
  for (const diag of tab.diagnostics) {
    for (let line = diag.startLine; line <= diag.endLine; line++) {
      markers.push({
        line,
        severity: diag.severity,
        diagnosticId: diag.id
      });
    }
  }
  for (const pat of tab.patterns) {
    for (let line = pat.startLine; line <= pat.endLine; line++) {
      markers.push({
        line,
        severity: 'pattern',
        patternId: pat.id,
        patternKind: pat.kind,
        patternSeverity: pat.severity
      });
    }
  }
  return markers;
}

export function CodeEditorPane(props: Props) {
  const { tab } = props;
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const [lineCount, setLineCount] = useState(() => tab.content.split(/\r?\n/).length);
  const [highlightLines, setHighlightLines] = useState<Token[][]>(() => tokenizeContent(tab.content, tab.language));
  const [selectionText, setSelectionText] = useState('');

  useEffect(() => {
    setLineCount(tab.content.split(/\r?\n/).length);
  }, [tab.content]);

  useEffect(() => {
    setHighlightLines(tokenizeContent(tab.content, tab.language));
  }, [tab.content, tab.language]);

  useEffect(() => {
    if (textareaRef.current && overlayRef.current) {
      // Sincronizar scroll.
      overlayRef.current.scrollTop = textareaRef.current.scrollTop;
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  });

  const markers = useMemo(() => gutterForTab(tab), [tab]);

  const handleScroll = useCallback(() => {
    if (overlayRef.current && textareaRef.current) {
      overlayRef.current.scrollTop = textareaRef.current.scrollTop;
      overlayRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);
  const handleChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (tab.state === 'readonly') return;
    props.onChange(event.target.value);
  };

  const handleSelect = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    if (start === end) {
      setSelectionText('');
      props.onSelect(null);
      return;
    }
    const text = ta.value.slice(start, end);
    setSelectionText(text);
    const startPos = positionFromIndex(tab.content, start);
    const endPos = positionFromIndex(tab.content, end);
    props.onSelect({
      path: tab.path,
      startLine: startPos.line,
      endLine: endPos.line,
      startColumn: startPos.column,
      endColumn: endPos.column,
      text
    });
  };

  const handleKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
      event.preventDefault();
      props.onRequestSave();
    }
  };

  const onGutterClick = (marker: MarkerEntry) => {
    if (marker.severity === 'pattern' && marker.patternId) {
      const pat = tab.patterns.find((p) => p.id === marker.patternId);
      if (pat) props.onRequestPattern(pat);
    } else if (marker.diagnosticId) {
      const diag = tab.diagnostics.find((d) => d.id === marker.diagnosticId);
      if (diag) props.onRequestDiagnostic(diag);
    }
  };

  const handleContextMenu = (event: MouseEvent<HTMLDivElement>) => {
    if (!props.onContextMenu) return;
    event.preventDefault();
    props.onContextMenu(event, props.selectedRange);
  };

  const tabIndent = tab.language === 'python' ? ' '.repeat(CHARS_PER_INDENT) : ' '.repeat(CHARS_PER_INDENT);
  const lineNumberWidth = Math.max(2, String(lineCount).length);

  const overlayStyle: CSSProperties = {
    lineHeight: `${LINE_HEIGHT}px`,
    fontSize: `${FONT_SIZE}px`,
    whiteSpace: 'pre',
    fontFamily: 'ui-monospace, "JetBrains Mono", "Fira Code", Consolas, monospace',
    tabSize: 2
  };

  return (
    <div className="code-editor" data-language={tab.language}>
      <div className="code-editor-gutter" aria-hidden="true">
        <div className="code-editor-gutter-lines" style={{ lineHeight: `${LINE_HEIGHT}px`, fontSize: `${FONT_SIZE}px` }}>
          {Array.from({ length: lineCount }, (_, i) => i + 1).map((line) => {
            const marker = markers.find((m) => m.line === line);
            return (
              <div key={line} className="code-editor-gutter-line">
                <span className="code-editor-gutter-number">{padLine(line, lineCount)}</span>
                <span
                  className={`code-editor-gutter-marker ${marker ? `state-${marker.severity}` : ''}`}
                  onClick={() => marker && onGutterClick(marker)}
                  title={marker && (marker.severity === 'pattern' && marker.patternId
                    ? (tab.patterns.find((p) => p.id === marker.patternId)?.title || 'patrón')
                    : tab.diagnostics.find((d) => d.id === marker.diagnosticId)?.message || 'diagnóstico')}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="code-editor-surface" onContextMenu={handleContextMenu}>
        <div className="code-editor-overlay" ref={overlayRef} style={overlayStyle} aria-hidden="true">
          {highlightLines.map((tokens, idx) => (
            <div key={idx} className="code-editor-overlay-line">
              {tokens.map((token, tokenIdx) => (
                <span key={tokenIdx} className={`code-token code-token-${token.kind}`}>{token.text || ' '}</span>
              ))}
              {tokens.length === 0 && <span> </span>}
            </div>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          className="code-editor-textarea"
          value={tab.content}
          spellCheck={false}
          onChange={handleChange}
          onSelect={handleSelect}
          onKeyDown={handleKey}
          onClick={handleSelect}
          onScroll={handleScroll}
          readOnly={tab.state === 'readonly'}
          aria-label={`Editor de código: ${tab.label}`}
          style={{ ...overlayStyle, tabSize: 2 }}
        />
      </div>
      {selectionText && (
        <div className="code-editor-selection-tip" aria-live="polite">
          {selectionText.length} caracteres · línea {props.selectedRange?.startLine}-{props.selectedRange?.endLine}
        </div>
      )}
      <div className="code-editor-lang-hint" aria-hidden="true">{tab.language.toUpperCase()} · {tabIndent}tab=2 · click derecho para acciones</div>
    </div>
  );
}

function positionFromIndex(content: string, index: number): { line: number; column: number } {
  let line = 1;
  let column = 1;
  for (let i = 0; i < index && i < content.length; i++) {
    if (content[i] === '\n') {
      line += 1;
      column = 1;
    } else {
      column += 1;
    }
  }
  return { line, column };
}
