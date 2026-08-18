export function workspaceScopedStorageKey(workspaceRoot: string, suffix: string): string {
  const cleanRoot = String(workspaceRoot || '').trim();
  return cleanRoot ? `bago.workspace.${cleanRoot}::${suffix}` : `bago.workspace.global::${suffix}`;
}

export function workspaceChatModeStorageKey(workspaceRoot: string): string {
  return workspaceScopedStorageKey(workspaceRoot, 'chat-mode');
}

function safeSessionStorage(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readWorkspaceStorageValue(workspaceRoot: string, suffix: string): string {
  const storage = safeSessionStorage();
  if (!storage) return '';
  try {
    return storage.getItem(workspaceScopedStorageKey(workspaceRoot, suffix)) || '';
  } catch {
    return '';
  }
}

export function writeWorkspaceStorageValue(workspaceRoot: string, suffix: string, value: string): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.setItem(workspaceScopedStorageKey(workspaceRoot, suffix), value);
  } catch {
    // storage unavailable
  }
}

export function removeWorkspaceStorageValue(workspaceRoot: string, suffix: string): void {
  const storage = safeSessionStorage();
  if (!storage) return;
  try {
    storage.removeItem(workspaceScopedStorageKey(workspaceRoot, suffix));
  } catch {
    // storage unavailable
  }
}
