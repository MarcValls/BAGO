// fileTypePresentation.ts
// Centralized file type detection and presentation mapping.
// All color and icon decisions live here — FileExplorer must not contain hardcoded type logic.

export type FileTypeKind =
  | 'javascript'
  | 'typescript'
  | 'python'
  | 'json'
  | 'html'
  | 'css'
  | 'markdown'
  | 'shell'
  | 'config'
  | 'image'
  | 'default';

export interface FilePresentation {
  kind: FileTypeKind;
  label: string;
  colorToken: string; // CSS variable name under --color-file-*
  iconName: string;   // matches IconName in Icon.tsx
}

// Ordered: special names first, then extensions
const FILE_TYPE_RULES: Array<{
  test: (name: string, ext: string) => boolean;
  presentation: FilePresentation;
}> = [
  {
    test: (name) => name === '.gitignore',
    presentation: { kind: 'config', label: 'Git ignore', colorToken: 'var(--color-file-config)', iconName: 'git' },
  },
  {
    test: (name) => name === '.env',
    presentation: { kind: 'config', label: 'Env', colorToken: 'var(--color-file-config)', iconName: 'settings' },
  },
  {
    test: (name) => name.startsWith('.env.')!,
    presentation: { kind: 'config', label: 'Env', colorToken: 'var(--color-file-config)', iconName: 'settings' },
  },
  {
    test: (_, ext) => ext === '.js' || ext === '.jsx',
    presentation: { kind: 'javascript', label: 'JavaScript', colorToken: 'var(--color-file-javascript)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.ts' || ext === '.tsx',
    presentation: { kind: 'typescript', label: 'TypeScript', colorToken: 'var(--color-file-typescript)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.py',
    presentation: { kind: 'python', label: 'Python', colorToken: 'var(--color-file-python)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.json',
    presentation: { kind: 'json', label: 'JSON', colorToken: 'var(--color-file-json)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.html' || ext === '.htm',
    presentation: { kind: 'html', label: 'HTML', colorToken: 'var(--color-file-html)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.css',
    presentation: { kind: 'css', label: 'CSS', colorToken: 'var(--color-file-css)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.md' || ext === '.mdx',
    presentation: { kind: 'markdown', label: 'Markdown', colorToken: 'var(--color-file-markdown)', iconName: 'file' },
  },
  {
    test: (_, ext) => ext === '.sh' || ext === '.bash' || ext === '.zsh',
    presentation: { kind: 'shell', label: 'Shell', colorToken: 'var(--color-file-shell)', iconName: 'terminal' },
  },
  {
    test: (_, ext) => ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico'].includes(ext),
    presentation: { kind: 'image', label: 'Image', colorToken: 'var(--color-file-image)', iconName: 'image' },
  },
  {
    test: (_, ext) => ['.lock', '.toml', '.yaml', '.yml', '.ini', '.cfg'].includes(ext),
    presentation: { kind: 'config', label: 'Config', colorToken: 'var(--color-file-config)', iconName: 'settings' },
  },
];

function getExtension(name: string): string {
  const lastDot = name.lastIndexOf('.');
  if (lastDot <= 0) return '';
  return name.slice(lastDot).toLowerCase();
}

export function getFilePresentation(name: string, isDirectory: boolean): FilePresentation {
  if (isDirectory) {
    return { kind: 'default', label: 'Folder', colorToken: 'var(--color-file-default)', iconName: 'folder' };
  }

  const ext = getExtension(name);
  const lower = name.toLowerCase();

  for (const rule of FILE_TYPE_RULES) {
    if (rule.test(lower, ext)) {
      return rule.presentation;
    }
  }

  return { kind: 'default', label: 'File', colorToken: 'var(--color-file-default)', iconName: 'file' };
}
