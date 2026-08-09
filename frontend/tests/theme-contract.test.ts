import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const tokens = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8');
const components = readFileSync(new URL('../src/styles/components.css', import.meta.url), 'utf8');
const controlPlane = readFileSync(new URL('../src/app/ControlPlane.tsx', import.meta.url), 'utf8');

describe('appearance theme contract', () => {
  it('keeps the light palette in a single source of truth', () => {
    const declarations = `${tokens}\n${components}`.match(/\.app-root\.theme-light\s*\{/g) || [];
    expect(declarations).toHaveLength(1);
    expect(tokens).toMatch(/:root\.theme-light,\s*\n\.app-root\.theme-light\s*\{/);
  });

  it('applies the active palette to document-level dialogs', () => {
    expect(controlPlane).toContain("document.documentElement");
    expect(controlPlane).toContain("root.classList.toggle('theme-light'");
    expect(controlPlane).toContain("root.style.colorScheme = uiState.appearanceTheme");
  });

  it('defines adaptive surfaces for controls and visual canvases', () => {
    for (const token of ['--control-bg', '--canvas-bg', '--canvas-grid', '--canvas-node', '--surface-glass']) {
      expect(tokens).toContain(`${token}:`);
    }
    expect(tokens).toMatch(/\.app-root\s*\{[\s\S]*?--canvas-bg:/);
  });

  it('does not reintroduce the dark surfaces that broke light mode', () => {
    for (const hardcoded of [
      'background: rgba(5,8,13,.62);',
      'background: rgba(18,25,37,.95);',
      'background: rgba(14,19,29,.94);',
      'background: rgba(10,14,21,.7);',
      '  #0d121b;'
    ]) {
      expect(components).not.toContain(hardcoded);
    }
  });
});
