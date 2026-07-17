export interface WorkspaceSelectionResult {
  ok?: boolean;
  canceled?: boolean;
  path?: string;
  filePath?: string;
  filePaths?: string[];
  message?: string;
}

export interface WorkspaceLinkResult {
  ok?: boolean;
  canceled?: boolean;
  message?: string;
  root?: string;
  path?: string;
  data?: unknown;
  stdout?: string;
  stderr?: string;
}

export interface BagoElectronBridge {
  chooseWorkspaceRoot?: (options?: { defaultPath?: string; basePath?: string; initialPath?: string }) => Promise<WorkspaceSelectionResult | null>;
  chooseProjectRoot?: (options?: { defaultPath?: string; basePath?: string; initialPath?: string }) => Promise<WorkspaceSelectionResult | null>;
  linkProjectRoot?: (root: string) => Promise<WorkspaceLinkResult | null>;
  getManagerUrl?: () => Promise<string> | string;
  onInstanceActive?: (callback: (payload: { ok?: boolean; message?: string }) => void) => void;
}

declare global {
  interface Window {
    bagoElectron?: BagoElectronBridge;
  }
}

export {};
