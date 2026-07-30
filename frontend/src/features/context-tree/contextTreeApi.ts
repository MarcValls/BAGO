// Cliente del ContextTreeModule. Usa los endpoints existentes
// (/files/read, /files/write, /files/list) y los catálogos disponibles
// (sources, evidence, memory, interpret rules) para alimentar el Banco
// contextual. No añade endpoints nuevos.
import type { BagoClient } from '@/api/client';
import type {
  ContextBankItem,
  ContextBankSnapshot,
  ContextCompiledPack,
  ContextPack,
  ContextPatchRequest,
  ContextReceipt,
  ContextTree
} from './contextTreeTypes';

export const CONTEXT_DIR = '.bago/context';
export const CONTEXT_TREE_FILE = `${CONTEXT_DIR}/context-tree.json`;
export const CONTEXT_PACKS_FILE = `${CONTEXT_DIR}/context-packs.json`;
export const CONTEXT_PROPOSALS_FILE = `${CONTEXT_DIR}/context-proposals.json`;
export const CONTEXT_RECEIPTS_FILE = `${CONTEXT_DIR}/context-receipts.jsonl`;
export const CONTEXT_COMPILED_FILE = `${CONTEXT_DIR}/compiled-context.md`;

// Prefijos que el runtime de BAGO usa internamente para metadatos,
// estado, conocimiento y bundle. Nunca deben aparecer como items del
// Banco porque no son archivos del scope del usuario.
const BAGO_METADATA_PREFIXES = ['.bago', '.gabo', 'node_modules', '.git', '__pycache__'];

function isBagoMetadataPath(rawPath: string): boolean {
  if (!rawPath) return false;
  // Normalizar separadores a "/" y eliminar el prefijo "workspace/"
  // que el bridge antepone al mirror.
  const normalized = rawPath.replace(/\\/g, '/').replace(/^workspace\//, '');
  // El path es una serie de segmentos; miramos el primero (la raíz
  // inmediata dentro del mirror/scope). Si empieza por un prefijo
  // reservado, es metadato de BAGO.
  const head = normalized.split('/').filter(Boolean)[0] || '';
  return BAGO_METADATA_PREFIXES.some((prefix) => head === prefix || head.startsWith(prefix));
}

function nowStamp(): string {
  return new Date().toISOString();
}

function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36).slice(-4)}`;
}

function detectLanguageFromName(name: string): string {
  const ext = String(name || '').split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', json: 'json', md: 'markdown', css: 'css', html: 'html',
    sh: 'shell', bash: 'shell', yml: 'yaml', yaml: 'yaml', toml: 'toml', env: 'dotenv'
  };
  return map[ext] || 'text';
}

export { detectLanguageFromName };

async function readJson<T>(client: BagoClient, path: string, fallback: T): Promise<T> {
  const result = await client.readFile(path, { optional: true });
  if (!result || typeof result !== 'object') return fallback;
  const content = (result as { content?: unknown }).content;
  if (typeof content !== 'string' || !content.trim()) return fallback;
  return JSON.parse(content) as T;
}

async function writeJson(client: BagoClient, path: string, data: unknown): Promise<void> {
  const content = JSON.stringify(data, null, 2);
  await client.writeFile(path, content);
}

async function readText(client: BagoClient, path: string): Promise<string> {
  const result = await client.readFile(path, { optional: true });
  if (!result || typeof result !== 'object') return '';
  return String((result as { content?: unknown }).content || '');
}

async function writeText(client: BagoClient, path: string, content: string): Promise<void> {
  await client.writeFile(path, content);
}

// --------- Árbol ---------

export async function loadContextTree(client: BagoClient): Promise<ContextTree | null> {
  return readJson<ContextTree | null>(client, CONTEXT_TREE_FILE, null);
}

export async function saveContextTree(client: BagoClient, tree: ContextTree): Promise<void> {
  await writeJson(client, CONTEXT_TREE_FILE, tree);
}

export function buildDefaultTree(): ContextTree {
  const id = newId('ctree');
  const rootId = newId('node');
  const nodes: Record<string, ContextTree['nodes'][string]> = {};
  const stamp = nowStamp();
  nodes[rootId] = {
    id: rootId,
    treeId: id,
    parentId: null,
    type: 'root',
    status: 'active',
    title: 'Contexto raíz',
    summary: 'Raíz del árbol de contexto del workspace activo.',
    priority: 'high',
    sourceRefs: [],
    evidenceRefs: [],
    linkedNodeIds: [],
    conflictNodeIds: [],
    tags: ['root'],
    metadata: {},
    createdBy: 'system',
    updatedBy: 'system',
    createdAt: stamp,
    updatedAt: stamp
  };
  return {
    id,
    name: `Árbol ${new Date().toLocaleString()}`,
    archived: false,
    createdAt: stamp,
    updatedAt: stamp,
    rootId,
    nodes
  };
}

// --------- Packs ---------

export async function loadContextPacks(client: BagoClient): Promise<ContextPack[]> {
  return readJson<ContextPack[]>(client, CONTEXT_PACKS_FILE, []);
}

export async function saveContextPacks(client: BagoClient, packs: ContextPack[]): Promise<void> {
  await writeJson(client, CONTEXT_PACKS_FILE, packs);
}

export function buildDefaultPack(tree: ContextTree): ContextPack {
  return {
    id: newId('pack'),
    treeId: tree.id,
    name: 'Pack principal',
    status: 'draft',
    nodeIds: [],
    weightTokens: 0,
    conflicts: 0,
    proposals: 0,
    staleCount: 0
  };
}

// --------- Propuestas / patch requests ---------

export async function loadContextPatchRequests(client: BagoClient): Promise<ContextPatchRequest[]> {
  return readJson<ContextPatchRequest[]>(client, CONTEXT_PROPOSALS_FILE, []);
}

export async function saveContextPatchRequests(client: BagoClient, requests: ContextPatchRequest[]): Promise<void> {
  await writeJson(client, CONTEXT_PROPOSALS_FILE, requests);
}

// --------- Receipts (JSONL) ---------

export async function appendContextReceipt(client: BagoClient, receipt: ContextReceipt): Promise<void> {
  const existing = await readText(client, CONTEXT_RECEIPTS_FILE);
  const line = `${JSON.stringify(receipt)}\n`;
  await writeText(client, CONTEXT_RECEIPTS_FILE, `${existing}${line}`);
}

export async function loadContextReceipts(client: BagoClient): Promise<ContextReceipt[]> {
  const text = await readText(client, CONTEXT_RECEIPTS_FILE);
  if (!text.trim()) return [];
  const out: ContextReceipt[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      out.push(JSON.parse(line) as ContextReceipt);
    } catch {
      // Ignora líneas mal formadas: nunca debe romper la carga.
    }
  }
  return out;
}

// --------- Compilado ---------

export async function saveCompiledContext(client: BagoClient, compiled: ContextCompiledPack): Promise<void> {
  await writeText(client, CONTEXT_COMPILED_FILE, compiled.markdown);
}

export async function loadCompiledContext(client: BagoClient): Promise<string> {
  return readText(client, CONTEXT_COMPILED_FILE);
}

// --------- Banco contextual: carga desde endpoints existentes ---------

function asArray<T = Record<string, unknown>>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

export const CONTEXT_BANK_MANUAL_FILE = `${CONTEXT_DIR}/context-bank-manual.json`;
export const CONTEXT_SOURCE_DIRECTORIES_FILE = `${CONTEXT_DIR}/context-source-directories.json`;

export async function loadContextBankManual(client: BagoClient): Promise<ContextBankItem[]> {
  return readJson<ContextBankItem[]>(client, CONTEXT_BANK_MANUAL_FILE, []);
}

export async function saveContextBankManual(client: BagoClient, items: ContextBankItem[]): Promise<void> {
  await writeJson(client, CONTEXT_BANK_MANUAL_FILE, items);
}

export async function loadSourceDirectories(client: BagoClient): Promise<import('./contextTreeTypes').SourceDirectory[]> {
  return readJson<import('./contextTreeTypes').SourceDirectory[]>(client, CONTEXT_SOURCE_DIRECTORIES_FILE, []);
}

export async function saveSourceDirectories(client: BagoClient, items: import('./contextTreeTypes').SourceDirectory[]): Promise<void> {
  await writeJson(client, CONTEXT_SOURCE_DIRECTORIES_FILE, items);
}

export async function loadContextBank(client: BagoClient): Promise<ContextBankSnapshot> {
  const errors: string[] = [];
  const result: ContextBankSnapshot = {
    files: [],
    sources: [],
    claims: [],
    receipts: [],
    memory: [],
    history: [],
    rules: [],
    project: [],
    manual: [],
    errors
  };
  // Files
  try {
    const payload = await client.listFiles();
    const entries = asArray<Record<string, unknown>>(payload.entries || payload.files || payload);
    for (const entry of entries) {
      const path = String(entry.path || entry.name || '').trim();
      if (!path) continue;
      // CANON[CTX-021]: el bridge lista el mirror del workspace, que
      // contiene archivos de BAGO (.bago/...) además de los del scope
      // del usuario. Filtramos los prefijos de metadatos para que el
      // Banco solo muestre los archivos del workspace real.
      if (isBagoMetadataPath(path)) continue;
      const type = String(entry.type || '').toLowerCase();
      const isDir = ['directory', 'dir', 'folder'].includes(type);
      result.files.push({
        id: `file:${path}`,
        kind: isDir ? 'workspace_directory' : 'workspace_file',
        title: path.split('/').pop() || path,
        origin: 'workspace',
        path,
        tags: isDir ? ['carpeta'] : undefined,
        raw: entry,
        suggestedBranch: isDir ? 'source' : 'source'
      });
    }
  } catch (error) {
    errors.push(`files: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Sources
  try {
    const payload = await client.listSources();
    const entries = asArray<Record<string, unknown>>(payload.sources || payload.entries || payload);
    for (const entry of entries) {
      const path = String(entry.path || entry.label || entry.key || '').trim();
      if (!path) continue;
      result.sources.push({
        id: `source:${path}`,
        kind: 'source_root',
        title: String(entry.label || path.split(/[\\/]/).pop() || path),
        origin: 'fuente',
        path,
        raw: entry,
        suggestedBranch: 'source'
      });
    }
  } catch (error) {
    errors.push(`sources: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Claims
  try {
    const payload = await client.listEvidenceClaims();
    const entries = asArray<Record<string, unknown>>(payload.claims || payload.entries || payload);
    for (const entry of entries) {
      const id = String(entry.claim_id || entry.id || '').trim();
      if (!id) continue;
      result.claims.push({
        id: `claim:${id}`,
        kind: 'claim',
        title: String(entry.title || entry.summary || `Claim ${id}`).slice(0, 90),
        origin: 'evidence',
        path: id,
        raw: entry,
        suggestedBranch: 'evidence'
      });
    }
  } catch (error) {
    errors.push(`claims: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Receipts
  try {
    const payload = await client.listEvidenceReceipts();
    const entries = asArray<Record<string, unknown>>(payload.receipts || payload.entries || payload);
    for (const entry of entries) {
      const id = String(entry.receipt_id || entry.id || '').trim();
      if (!id) continue;
      result.receipts.push({
        id: `receipt:${id}`,
        kind: 'receipt',
        title: String(entry.summary || entry.message || `Receipt ${id}`).slice(0, 90),
        origin: 'evidence',
        path: id,
        raw: entry,
        suggestedBranch: 'evidence'
      });
    }
  } catch (error) {
    errors.push(`receipts: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Memory
  try {
    const payload = await client.listMemory();
    const entries = asArray<Record<string, unknown>>(payload.entries || payload.items || payload);
    for (const entry of entries) {
      const id = String(entry.id || entry.key || '').trim() || newId('mem');
      const text = String(entry.summary || entry.text || entry.content || '').slice(0, 90);
      result.memory.push({
        id: `memory:${id}`,
        kind: 'memory',
        title: text || `Memoria ${id}`,
        origin: 'memory',
        path: id,
        raw: entry,
        suggestedBranch: 'note'
      });
    }
  } catch (error) {
    errors.push(`memory: ${error instanceof Error ? error.message : String(error)}`);
  }
  // History
  try {
    const payload = await client.getHistory();
    const history = asRecord(payload);
    const entries = asArray<Record<string, unknown>>(history?.messages || history?.entries || payload);
    for (const entry of entries.slice(0, 50)) {
      const text = String(entry.content || entry.text || entry.message || '').trim().slice(0, 80);
      if (!text) continue;
      result.history.push({
        id: `history:${entry.id || text.slice(0, 16)}`,
        kind: 'history',
        title: text,
        origin: 'history',
        raw: entry,
        suggestedBranch: 'note'
      });
    }
  } catch (error) {
    errors.push(`history: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Interpret rules
  try {
    const payload = await client.getInterpretRules();
    const entries = asArray<Record<string, unknown>>(payload.rules || payload.entries || payload);
    for (const entry of entries) {
      const id = String(entry.id || entry.name || '').trim();
      if (!id) continue;
      result.rules.push({
        id: `rule:${id}`,
        kind: 'rule',
        title: String(entry.name || entry.title || id).slice(0, 90),
        origin: 'interpret',
        path: id,
        raw: entry,
        suggestedBranch: 'rule'
      });
    }
  } catch (error) {
    errors.push(`rules: ${error instanceof Error ? error.message : String(error)}`);
  }
  // Project status
  try {
    const payload = await client.getProjectStatus();
    const data = asRecord(payload.data) || asRecord(payload) || {};
    const id = String(data.id || data.name || 'project');
    result.project.push({
      id: `project:${id}`,
      kind: 'project_status',
      title: String(data.name || data.summary || 'Estado del proyecto').slice(0, 90),
      origin: 'project',
      path: id,
      raw: data,
      suggestedBranch: 'risk'
    });
  } catch (error) {
    errors.push(`project: ${error instanceof Error ? error.message : String(error)}`);
  }
  // CANON[CTX-022]: items manuales persistidos en
  // `.bago/context/context-bank-manual.json`. El usuario puede
  // vincular paths explícitos que no están en `/files/list` (por
  // ejemplo, directorios del scope real que el mirror aún no
  // expone, o rutas externas).
  try {
    const manual = await loadContextBankManual(client);
    if (Array.isArray(manual)) {
      for (const item of manual) {
        if (item && item.id && item.title) {
          result.manual.push(item);
        }
      }
    }
  } catch (error) {
    errors.push(`manual: ${error instanceof Error ? error.message : String(error)}`);
  }
  return result;
}

// --------- Envío de pack al chat ---------

export interface ChatSendResult {
  ok: boolean;
  message?: string;
  receiptId?: string;
}

export async function sendCompiledContextToChat(
  client: BagoClient,
  pack: ContextPack,
  compiled: string,
  extraMessage?: string
): Promise<ChatSendResult> {
  const header = `[CONTEXT_PACK ${pack.id} · ${pack.name} · ${pack.weightTokens} tokens]`;
  const body = [header, '', compiled].join('\n');
  const message = extraMessage ? `${body}\n\n${extraMessage}` : body;
  try {
    const response = await client.sendChat(message);
    return {
      ok: true,
      message: String(response.message || response.state || 'enviado'),
      receiptId: String(response.receipt_id || response.receiptId || '')
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : String(error)
    };
  }
}

export function newPatchId(): string {
  return newId('patch');
}

export function newNodeId(): string {
  return newId('node');
}
