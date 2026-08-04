import { describe, expect, it } from 'vitest';
import { normalizeActiveSection } from '../src/state/uiStore';

describe('canonical UI navigation', () => {
  it('migrates the legacy chat destination to Inicio', () => {
    expect(normalizeActiveSection('chat')).toBe('home');
  });

  it('keeps current control-plane destinations unchanged', () => {
    expect(normalizeActiveSection('context')).toBe('context');
    expect(normalizeActiveSection('workspace')).toBe('workspace');
  });
});
