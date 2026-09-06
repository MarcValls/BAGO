// @vitest-environment happy-dom
import { beforeEach, describe, expect, it } from 'vitest';
import {
  loadUiState,
  persistUiState,
  createDefaultUiState,
  normalizeActiveSection
} from '../src/state/uiStore';

describe('canonical UI navigation', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('migrates the legacy chat destination to Inicio', () => {
    expect(normalizeActiveSection('chat')).toBe('home');
  });

  it('migrates the legacy graph destination to Pipeline', () => {
    expect(normalizeActiveSection('graph')).toBe('pipeline');
  });

  it('keeps current control-plane destinations unchanged', () => {
    expect(normalizeActiveSection('context')).toBe('context');
    expect(normalizeActiveSection('workspace')).toBe('workspace');
  });

  it('defaults chatDocked to false', () => {
    const state = loadUiState();
    expect(state.chatDocked).toBe(false);
  });

  it('persists and reloads the chat dock flag', () => {
    const state = { ...createDefaultUiState(), chatDocked: true };
    persistUiState(state);
    const loaded = loadUiState();
    expect(loaded.chatDocked).toBe(true);
  });

  it('starts with the navigation labels visible so destinations are discoverable', () => {
    // Colapsado por defecto el sidebar sólo pinta iconos sin etiqueta, lo que
    // obliga a descubrir los destinos por prueba y error en el primer arranque.
    expect(loadUiState().sidebarCollapsed).toBe(false);
  });

  it('respects a stored preference for a collapsed sidebar', () => {
    persistUiState({ ...createDefaultUiState(), sidebarCollapsed: true });
    expect(loadUiState().sidebarCollapsed).toBe(true);
  });
});
