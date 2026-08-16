// src/features/workspace/workspaceApi.ts
// Cliente HTTP para archivos y diagnóstico del editor de Workspace.
// Usa el cliente BAGO existente para no añadir endpoints nuevos.

import type { BagoClient } from '@/api/client';
import type { Language } from './workspaceTypes';
import { detectLanguage } from './detectLanguage';

export interface FileReadResult {
  path: string;
  content: string;
  encoding?: string;
  size?: number;
  modified?: string;
  language: Language;
}

export interface FileListEntry {
  path: string;
  name: string;
  kind?: 'directory' | 'file';
  type?: 'directory' | 'file';
  size?: number;
  modified?: string;
}

export class WorkspaceApiError extends Error {
  status?: number;
  path?: string;
  constructor(message: string, status?: number, path?: string) {
    super(message);
    this.name = 'WorkspaceApiError';
    this.status = status;
    this.path = path;
  }
}

export async function listWorkspaceFiles(
  client: BagoClient,
  root: string
): Promise<FileListEntry[]> {
  if (!root) return [];
  const response = await client.request<FileListEntry[] | { entries: FileListEntry[] } | { files: FileListEntry[] }>(
    `/files/list?root=${encodeURIComponent(root)}`,
    { method: 'GET' }
  );
  if (Array.isArray(response)) return response;
  if (response && typeof response === 'object') {
    const obj = response as { entries?: FileListEntry[]; files?: FileListEntry[] };
    if (Array.isArray(obj.entries)) return obj.entries;
    if (Array.isArray(obj.files)) return obj.files;
  }
  return [];
}export async function readWorkspaceFile(
  client: BagoClient,
  path: string
): Promise<FileReadResult> {
  const response = await client.request<{ content: string; size?: number; modified?: string; encoding?: string } | string>(
    `/files/read/${encodeURIComponent(path).replace(/%2F/g, '/')}`,
    { method: 'GET' }
  );
  let content = '';
  let size: number | undefined;
  let modified: string | undefined;
  let encoding: string | undefined;
  if (typeof response === 'string') {
    content = response;
  } else if (response && typeof response === 'object') {
    content = String(response.content || '');
    size = response.size;
    modified = response.modified;
    encoding = response.encoding;
  }
  return {
    path,
    content,
    encoding,
    size,
    modified,
    language: detectLanguage(path)
  };
}

export async function writeWorkspaceFile(
  client: BagoClient,
  path: string,
  content: string
): Promise<{ path: string; size: number; saved: string }> {
  const response = await client.request<{ path?: string; size?: number; saved?: string }>(
    '/files/write',
    {
      method: 'POST',
      body: JSON.stringify({ path, content, createDirs: true })
    }
  );
  return {
    path: response?.path || path,
    size: response?.size || content.length,
    saved: response?.saved || new Date().toISOString()
  };
}

export async function runCommand(
  client: BagoClient,
  command: string
): Promise<{ ok: boolean; output: string; error?: string }> {
  try {
    const response = await client.request<{ output?: string; result?: string; error?: string; ok?: boolean }>(
      '/api/v1/commands',
      {
        method: 'POST',
        body: JSON.stringify({ command, channel: 'ui-react', surface: 'ui-react' })
      }
    );
    return {
      ok: response?.ok !== false,
      output: String(response?.output || response?.result || ''),
      error: response?.error
    };
  } catch (error: unknown) {
    return {
      ok: false,
      output: '',
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

export async function runPythonCompile(
  client: BagoClient,
  path: string
): Promise<{ ok: boolean; output: string; error?: string }> {
  const result = await runCommand(client, `python -m py_compile "${path}"`);
  return result;
}

export async function runShellCheck(
  client: BagoClient,
  path: string
): Promise<{ ok: boolean; output: string; error?: string }> {
  const result = await runCommand(client, `shellcheck "${path}"`);
  return result;
}

export async function runTypeScriptCheck(
  client: BagoClient,
  path: string
): Promise<{ ok: boolean; output: string; error?: string }> {
  const result = await runCommand(client, `npx --no-install tsc --noEmit "${path}"`);
  return result;
}

export function hashContent(text: string): string {
  // FNV-1a 32-bit para evitar meter dependencias de hash.
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = (hash * 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}
