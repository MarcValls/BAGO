import type { ModuleAction, ModuleBridge, ModuleInspectResult, ModuleReadResult, ModuleRegistry, ModuleWriteResult } from '@/contracts/modules';

export function createModuleRegistry(modules: ModuleBridge[]): ModuleRegistry {
  const list = () => modules.slice();
  const get = (id: string) => modules.find((module) => module.id === id);

  const read = (id: string) => get(id)?.read();

  const write = async (id: string, payload?: Record<string, unknown>) => {
    const module = get(id);
    if (!module?.write) return undefined;
    return module.write(payload || {});
  };

  const inspect = async (id: string, target?: string) => {
    const module = get(id);
    if (!module?.inspect) return undefined;
    return module.inspect(target);
  };

  const invokeAction = async (id: string, actionId: string, payload?: Record<string, unknown>) => {
    const module = get(id);
    if (!module) return undefined;
    const action = module.actions.find((item) => item.id === actionId);
    if (!action || !action.enabled) return undefined;
    if (action.kind === 'read') return read(id);
    if (action.kind === 'inspect') return inspect(id, String(payload?.target || ''));
    if (action.kind === 'write') return write(id, payload || action.payload);
    if (action.kind === 'toggle') return write(id, { ...payload, enabled: Boolean(payload?.enabled ?? !(action.payload?.enabled ?? false)) });
    if (action.kind === 'refresh') return write(id, { ...payload, refresh: true });
    if (action.kind === 'select' || action.kind === 'navigate' || action.kind === 'register') return write(id, payload || action.payload);
    return undefined;
  };

  return { list, get, read, write, inspect, invokeAction };
}

export type { ModuleAction, ModuleBridge, ModuleInspectResult, ModuleReadResult, ModuleRegistry, ModuleWriteResult };
