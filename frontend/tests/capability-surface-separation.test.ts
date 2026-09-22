import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const sections = readFileSync(new URL('../src/features/sections.tsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
const bootstrap = readFileSync(new URL('../src/app/bootstrapSnapshot.ts', import.meta.url), 'utf8').replace(/\r\n/g, '\n');

describe('capability surface separation', () => {
  it('keeps the read-only anatomy behind the backend feature flag', () => {
    expect(bootstrap).toContain('features: readBooleanRecord(raw.features)');
    expect(sections).toContain("snapshot?.features?.capability_anatomy_v02 === true");
    expect(sections).toContain("pipelineView === 'capabilities'");
    expect(sections).toContain("pipelineView === 'packages'");
  });

  it('does not mount the executable package manager in the anatomy branch', () => {
    const anatomyStart = sections.indexOf("if (pipelineView === 'capabilities')");
    const packagesStart = sections.indexOf("if (pipelineView === 'packages')");
    expect(anatomyStart).toBeGreaterThanOrEqual(0);
    expect(packagesStart).toBeGreaterThan(anatomyStart);
    expect(sections.slice(anatomyStart, packagesStart)).not.toContain('<ExternalCapabilitiesPanel');
    expect(sections.slice(packagesStart)).toContain('<ExternalCapabilitiesPanel');
  });
});
