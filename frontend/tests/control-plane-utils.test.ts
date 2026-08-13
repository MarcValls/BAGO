import { describe, expect, it } from 'vitest';
import {
  commandKey,
  hashString,
  historyToTurns,
  normalizeWorkspaceHint,
  readSelectedWorkspace,
} from '../src/app/controlPlaneUtils';

describe('ControlPlane utilities', () => {
  it('normalizes workspace metadata paths without treating .bago as the project', () => {
    expect(normalizeWorkspaceHint('C:/work/demo/.bago/')).toBe('C:\\work\\demo');
    expect(normalizeWorkspaceHint('.gabo')).toBe('');
  });

  it('reads the first selected workspace and respects cancellation', () => {
    expect(readSelectedWorkspace({ filePaths: ['C:\\work\\demo'] })).toBe('C:\\work\\demo');
    expect(readSelectedWorkspace({ canceled: true, path: 'C:\\wrong' })).toBe('');
  });

  it('creates stable command and patch identifiers', () => {
    expect(commandKey('/context inspect')).toBe('context_inspect');
    expect(hashString('same patch')).toBe(hashString('same patch'));
    expect(hashString('same patch')).not.toBe(hashString('other patch'));
  });

  it('normalizes persisted history into presentation turns', () => {
    const turns = historyToTurns({
      messages: [{
        id: 'm1',
        role: 'assistant',
        content: 'Respuesta',
        provider: 'local',
        model: 'test',
        timestamp: '2026-08-12T10:00:00.000Z',
      }],
    });
    expect(turns).toHaveLength(1);
    expect(turns[0]).toMatchObject({ id: 'm1', role: 'assistant', text: 'Respuesta', provider: 'local', model: 'test' });
  });
});
