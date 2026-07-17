// src/features/workspace/detectCodePatterns.ts
// Heurísticas MVP para reconocimiento de patrones. Se ejecuta por
// archivo y produce entradas que se muestran en el panel Patrones y
// opcionalmente en el gutter del editor.

import type { Language, WorkspacePattern, PatternCategory } from './workspaceTypes';
import { detectLanguage } from './detectLanguage';

let counter = 0;
function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now()}-${counter}`;
}

interface PatternRule {
  category: PatternCategory;
  kind: string;
  title: string;
  severity: 'low' | 'medium' | 'high';
  suggestion?: string;
  // Encuentra la línea/columna donde aparece el patrón.
  match: (line: string, language: Language) => boolean;
  detail?: (line: string) => string;
}

const RULES: PatternRule[] = [
  {
    category: 'code',
    kind: 'todo-fixme',
    title: 'TODO/FIXME pendiente',
    severity: 'medium',
    suggestion: 'Resolver o convertir en tarea de Pipeline.',
    match: (line) => /\b(TODO|FIXME|XXX|HACK)\b/.test(line)
  },
  {
    category: 'code',
    kind: 'console-log',
    title: 'Console.log residual',
    severity: 'low',
    suggestion: 'Sustituir por logger centralizado o eliminar antes de producción.',
    match: (line, language) => language === 'javascript' || language === 'typescript' || language === 'jsx' || language === 'tsx'
      ? /\bconsole\.(log|debug|info|warn)\s*\(/.test(line)
      : false
  },
  {
    category: 'code',
    kind: 'any-usage',
    title: 'Uso de any',
    severity: 'medium',
    suggestion: 'Sustituir por un tipo concreto o unknown.',
    match: (line, language) => language === 'typescript' || language === 'tsx'
      ? /:\s*any\b/.test(line)
      : false
  },
  {
    category: 'code',
    kind: 'unused-import',
    title: 'Import no usado probable',
    severity: 'low',
    suggestion: 'Verificar uso y eliminar si no se referencia.',
    match: (line, language) => language === 'typescript' || language === 'javascript' || language === 'tsx' || language === 'jsx'
      ? /^\s*import\s+[\s\S]+from\s+['"][^'"]+['"];?\s*$/.test(line)
      : false
  },
  {
    category: 'code',
    kind: 'hardcoded-path',
    title: 'Ruta absoluta hardcoded',
    severity: 'medium',
    suggestion: 'Mover a configuración o variable de entorno.',
    match: (line) => /([A-Z]:\\\\|\/(?:home|usr|etc|var|tmp)\/)/.test(line)
  },
  {
    category: 'code',
    kind: 'hardcoded-endpoint',
    title: 'Endpoint hardcoded',
    severity: 'medium',
    suggestion: 'Mover a configuración central o variable de entorno.',
    match: (line) => /https?:\/\/[\w.-]+(?::\d+)?(?:\/[\w./-]*)?/.test(line)
  },
  {
    category: 'code',
    kind: 'dangerously-set',
    title: 'dangerouslySetInnerHTML',
    severity: 'high',
    suggestion: 'Validar contenido o sanitizar antes de inyectar.',
    match: (line) => /dangerouslySetInnerHTML/.test(line)
  },
  {
    category: 'ui',
    kind: 'data-inspect',
    title: 'Atributo data-inspect',
    severity: 'low',
    suggestion: 'BAGO usa data-inspect para inspección. No exponer datos sensibles.',
    match: (line) => /\bdata-inspect\b/.test(line)
  },
  {
    category: 'ui',
    kind: 'json-stringify',
    title: 'JSON.stringify en UI',
    severity: 'low',
    suggestion: 'Sustituir por formateador dedicado o estructura visible.',
    match: (line) => /JSON\.stringify\s*\(/.test(line)
  },
  {
    category: 'bago',
    kind: 'context-patch-handler',
    title: 'Manipulación del árbol contextual',
    severity: 'low',
    suggestion: 'Asegurar que applyContextPatch emite receipt y before snapshot.',
    match: (line) => /applyContextPatch|contextPatchRequest/.test(line)
  },
  {
    category: 'bago',
    kind: 'endpoint-not-registered',
    title: 'Endpoint BAGO no registrado',
    severity: 'medium',
    suggestion: 'Registrar endpoint en backend/.bago/api/bridge.py antes de invocarlo.',
    match: (line) => /\/api\/v1\/[a-zA-Z0-9_-]+/.test(line)
  },
  {
    category: 'security',
    kind: 'destructive-without-confirm',
    title: 'Acción destructiva detectable',
    severity: 'medium',
    suggestion: 'Pedir confirmación antes de eliminar o sobrescribir.',
    match: (line) => /\b(delete|remove|drop|truncate|rm)\b/i.test(line)
  },
  {
    category: 'security',
    kind: 'unsafe-write',
    title: 'Escritura fuera del workspace',
    severity: 'high',
    suggestion: 'Validar que la ruta está dentro del workspace autorizado.',
    match: (line) => /fetch\s*\(\s*['"]\/(?!\/)/.test(line)
  }
];

export function detectPatterns(path: string, content: string): WorkspacePattern[] {
  const language = detectLanguage(path);
  const lines = content.split(/\r?\n/);
  const patterns: WorkspacePattern[] = [];
  lines.forEach((line, index) => {
    const lineNumber = index + 1;
    for (const rule of RULES) {
      if (!rule.match(line, language)) continue;
      const column = line.indexOf(line.match(/[A-Za-z0-9_/]/)?.[0] || '') + 1 || 1;
      patterns.push({
        id: nextId(rule.kind),
        path,
        category: rule.category,
        kind: rule.kind,
        title: rule.title,
        detail: rule.detail ? rule.detail(line) : line.trim().slice(0, 200),
        startLine: lineNumber,
        endLine: lineNumber,
        startColumn: column,
        endColumn: column + Math.max(1, line.length),
        severity: rule.severity,
        suggestion: rule.suggestion
      });
    }
  });
  return patterns;
}
