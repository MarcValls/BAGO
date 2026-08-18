// src/features/workspace/runLocalDiagnostics.ts
// Diagnóstico local MVP. Para JSON, validación sintáctica completa.
// Para el resto, marcamos las posiciones a partir de mensajes del
// backend o de heurísticas muy simples.

import type { Language, WorkspaceDiagnostic } from './workspaceTypes';
import { detectLanguage } from './detectLanguage';

let counter = 0;
function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now()}-${counter}`;
}

export function runLocalDiagnostics(path: string, content: string): WorkspaceDiagnostic[] {
  const language = detectLanguage(path);
  if (language === 'json') return diagnoseJson(path, content);
  // Para otros lenguajes el diagnóstico backend es preferible, pero
  // marcamos heurísticas útiles aquí (e.g. línea vacía final, etc.)
  return diagnoseGeneric(path, content, language);
}

function diagnoseJson(path: string, content: string): WorkspaceDiagnostic[] {
  const diagnostics: WorkspaceDiagnostic[] = [];
  if (!content.trim()) return diagnostics;
  try {
    JSON.parse(content);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    const position = parseJsonErrorPosition(message);
    diagnostics.push({
      id: nextId('json'),
      path,
      severity: 'error',
      startLine: position?.line || 1,
      endLine: position?.line || 1,
      startColumn: position?.column || 1,
      endColumn: (position?.column || 1) + 1,
      message: prettyJsonError(message),
      source: 'json',
      origin: 'local'
    });
  }
  return diagnostics;
}

function parseJsonErrorPosition(message: string): { line: number; column: number } | null {
  // Node message format: "...at position N (line M column K)"
  const lineMatch = message.match(/line\s+(\d+)/i);
  const colMatch = message.match(/column\s+(\d+)/i);
  if (lineMatch) {
    return {
      line: Math.max(1, parseInt(lineMatch[1], 10)),
      column: colMatch ? Math.max(1, parseInt(colMatch[1], 10)) : 1
    };
  }
  const posMatch = message.match(/position\s+(\d+)/i);
  if (posMatch) {
    // Sin línea, devolveremos {line:1, col:1} como fallback
    return { line: 1, column: parseInt(posMatch[1], 10) };
  }
  return null;
}

function prettyJsonError(message: string): string {
  return message.replace(/^JSON\.parse:?\s*/i, '').trim();
}

function diagnoseGeneric(_path: string, _content: string, _language: Language): WorkspaceDiagnostic[] {
  // Diagnóstico genérico vacío; el backend o las heurísticas de
  // patrones cubren el resto del MVP.
  return [];
}
