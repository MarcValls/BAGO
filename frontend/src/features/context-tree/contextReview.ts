import type { ContextNode, ContextNodeType } from './contextTreeTypes';

export type ContextCategoryType = Extract<ContextNodeType, 'intent' | 'source' | 'decision' | 'rule' | 'risk'>;
export type ContextReviewStatus = 'validated' | 'warning' | 'conflict';

export interface ContextReviewFinding {
  severity: 'info' | 'warning' | 'critical';
  field: string;
  message: string;
  suggestion: string;
}

export interface ContextReviewResult {
  status: ContextReviewStatus;
  summary: string;
  findings: ContextReviewFinding[];
}

export const CONTEXT_CATEGORIES: Array<{
  id: ContextCategoryType;
  label: string;
  singular: string;
  hint: string;
}> = [
  { id: 'intent', label: 'Intención', singular: 'intención', hint: 'Objetivo, alcance y resultado esperado del proyecto.' },
  { id: 'source', label: 'Fuentes', singular: 'fuente', hint: 'Archivos, referencias y origen verificable de la información.' },
  { id: 'decision', label: 'Decisiones', singular: 'decisión', hint: 'Elecciones tomadas, motivo y alternativas descartadas.' },
  { id: 'rule', label: 'Reglas', singular: 'regla', hint: 'Restricciones y criterios que deben mantenerse.' },
  { id: 'risk', label: 'Riesgos', singular: 'riesgo', hint: 'Problemas posibles, impacto y mitigación prevista.' }
];

const REVIEW_CRITERIA: Record<ContextCategoryType, string> = {
  intent: 'Comprueba claridad del objetivo, alcance, resultado medible y contradicciones.',
  source: 'Comprueba trazabilidad, vigencia, autoridad de la fuente y datos que falten.',
  decision: 'Comprueba decisión, motivo, alternativas, consecuencias y coherencia con el contexto.',
  rule: 'Comprueba que sea inequívoca, aplicable, verificable y que no contradiga otras reglas.',
  risk: 'Comprueba causa, impacto, probabilidad, mitigación y señales de seguimiento.'
};

export function buildContextReviewPrompt(type: ContextCategoryType, node: Pick<ContextNode, 'title' | 'summary' | 'body' | 'priority' | 'tags'>): string {
  return [
    '[BAGO_CONTEXT_REVIEW_JSON]',
    `Revisa esta ${CONTEXT_CATEGORIES.find((entry) => entry.id === type)?.singular || type} como auditor de contexto de proyecto.`,
    REVIEW_CRITERIA[type],
    'No modifiques el contenido ni inventes hechos. Señala incertidumbre y conflictos.',
    'Devuelve SOLO JSON válido con esta forma:',
    '{"status":"validated|warning|conflict","summary":"...","findings":[{"severity":"info|warning|critical","field":"title|summary|body|priority|tags","message":"...","suggestion":"..."}]}',
    `Título: ${node.title}`,
    `Resumen: ${node.summary}`,
    `Detalle: ${node.body || ''}`,
    `Prioridad: ${node.priority}`,
    `Tags: ${node.tags.join(', ') || '(ninguno)'}`
  ].join('\n');
}

export function parseContextReviewResponse(raw: string): ContextReviewResult | null {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1];
  const candidate = fenced || raw;
  const start = candidate.indexOf('{');
  const end = candidate.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  let value: unknown;
  try { value = JSON.parse(candidate.slice(start, end + 1)); } catch { return null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const status = String(record.status || '').toLowerCase() as ContextReviewStatus;
  if (!['validated', 'warning', 'conflict'].includes(status)) return null;
  const findings: ContextReviewFinding[] = [];
  for (const rawFinding of (Array.isArray(record.findings) ? record.findings : []).slice(0, 8)) {
    if (!rawFinding || typeof rawFinding !== 'object' || Array.isArray(rawFinding)) continue;
    const finding = rawFinding as Record<string, unknown>;
    const severityRaw = String(finding.severity || 'info').toLowerCase();
    findings.push({
      severity: severityRaw === 'critical' || severityRaw === 'warning' ? severityRaw : 'info',
      field: String(finding.field || 'general').trim().slice(0, 40),
      message: String(finding.message || '').trim().slice(0, 500),
      suggestion: String(finding.suggestion || '').trim().slice(0, 500)
    });
  }
  return {
    status,
    summary: String(record.summary || 'Revisión completada.').trim().slice(0, 800),
    findings: findings.filter((finding) => finding.message)
  };
}
