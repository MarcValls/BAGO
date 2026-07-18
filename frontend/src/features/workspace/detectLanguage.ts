// src/features/workspace/detectLanguage.ts
// Detección de lenguaje por extensión. Lenguajes cubiertos en el MVP.

import type { Language } from './workspaceTypes';

const EXTENSION_MAP: Record<string, Language> = {
  ts: 'typescript',
  tsx: 'tsx',
  js: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  jsx: 'jsx',
  py: 'python',
  json: 'json',
  jsonc: 'json',
  md: 'markdown',
  mdx: 'markdown',
  css: 'css',
  scss: 'css',
  html: 'html',
  htm: 'html',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  yml: 'yaml',
  yaml: 'yaml',
  toml: 'toml',
  env: 'dotenv'
};

export function detectLanguage(path: string): Language {
  const fileName = String(path || '').split(/[\\/]/).pop() || '';
  const dotIndex = fileName.lastIndexOf('.');
  if (dotIndex < 0) return 'text';
  const ext = fileName.slice(dotIndex + 1).toLowerCase();
  return EXTENSION_MAP[ext] || 'text';
}

export function languageLabel(language: Language): string {
  const labels: Record<Language, string> = {
    typescript: 'TypeScript',
    tsx: 'TSX',
    javascript: 'JavaScript',
    jsx: 'JSX',
    python: 'Python',
    json: 'JSON',
    markdown: 'Markdown',
    css: 'CSS',
    html: 'HTML',
    shell: 'Shell',
    yaml: 'YAML',
    toml: 'TOML',
    dotenv: 'dotenv',
    text: 'Texto',
    unknown: 'Texto'
  };
  return labels[language] || 'Texto';
}

export function languageForFileKind(path: string): Language {
  return detectLanguage(path);
}

export function isBinaryHeuristic(path: string): boolean {
  const ext = (String(path).split('.').pop() || '').toLowerCase();
  const binaryExts = new Set([
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'svg',
    'pdf', 'zip', 'tar', 'gz', 'tgz', 'rar', '7z',
    'exe', 'dll', 'so', 'dylib', 'bin',
    'mp3', 'mp4', 'wav', 'mov', 'avi', 'mkv',
    'ttf', 'otf', 'woff', 'woff2',
    'pkl', 'pyc', 'pyo'
  ]);
  return binaryExts.has(ext);
}
