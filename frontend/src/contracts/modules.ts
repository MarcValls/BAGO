import type { ActiveSection, SelectionRecord } from './backend';

export type ModuleId = ActiveSection | 'provider-center';

export type ModuleCapability =
  | 'read'
  | 'write'
  | 'inspect'
  | 'navigate'
  | 'refresh'
  | 'select'
  | 'toggle'
  | 'register';

export type ModuleActionKind = 'read' | 'write' | 'inspect' | 'navigate' | 'refresh' | 'select' | 'toggle' | 'register';

export interface ModuleAction {
  id: string;
  label: string;
  kind: ModuleActionKind;
  enabled: boolean;
  visible?: boolean;
  reasonDisabled?: string;
  payload?: Record<string, unknown>;
}

export interface ModuleReadResult<TData = unknown> {
  moduleId: ModuleId;
  label: string;
  state?: string;
  summary: string;
  data: TData;
}

export interface ModuleWriteResult<TData = unknown> {
  moduleId: ModuleId;
  ok: boolean;
  message?: string;
  data?: TData;
}

export interface ModuleInspectResult<TData = unknown> {
  moduleId: ModuleId;
  selection?: SelectionRecord;
  message?: string;
  data?: TData;
}

export interface ModuleBridge<TRead = unknown, TWrite = Record<string, unknown>, TInspect = unknown> {
  id: ModuleId;
  label: string;
  description?: string;
  state?: string;
  capabilities: ModuleCapability[];
  actions: ModuleAction[];
  read: () => ModuleReadResult<TRead>;
  write?: (payload: TWrite) => ModuleWriteResult | Promise<ModuleWriteResult>;
  inspect?: (target?: string) => ModuleInspectResult<TInspect> | Promise<ModuleInspectResult<TInspect>>;
}

export interface ModuleRegistry {
  list: () => ModuleBridge[];
  get: (id: ModuleId | string) => ModuleBridge | undefined;
  read: (id: ModuleId | string) => ModuleReadResult | undefined;
  write: (id: ModuleId | string, payload?: Record<string, unknown>) => Promise<ModuleWriteResult | undefined>;
  inspect: (id: ModuleId | string, target?: string) => Promise<ModuleInspectResult | undefined>;
  invokeAction: (id: ModuleId | string, actionId: string, payload?: Record<string, unknown>) => Promise<unknown>;
}
