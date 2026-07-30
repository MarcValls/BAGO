import { describe, expect, it } from 'vitest';
import { CapabilityContractError, validateCapabilitySnapshot } from '../src/modules/capability-anatomy/contract';

function fixture() {
  return {
    schema_version: '0.2',
    contract_version: 'bago.capability/v0.2',
    revision: 1,
    etag: 'etag',
    source: { authority: 'backend', provenance: 'test', generated_at: null },
    capability: { id: 'cap', name: 'Cap', version: '0.2.0', description: 'Test', definition_state: 'prepared', availability: 'available', tags: [] },
    pieces: [
      { id: 'in', name: 'In', type: 'input', purpose: 'Input' },
      { id: 'out', name: 'Out', type: 'output', purpose: 'Output' }
    ],
    routes: [{ id: 'route', steps: ['in', 'out'] }],
    governance: { authority: { decision: 'backend', execution: 'backend', verification: 'backend' }, action_policy: { allowed: [], blocked: [] } },
    runtime_snapshot: { source: 'none', run_state: 'not_started', selected_piece_id: null, active_route_id: null, execution_id: null, receipt_id: null, observed_at: null },
    host_binding: { host: 'BAGO', surface: 'graph', mode: 'read_only', feature_flag: 'capability_anatomy_v02', persistence_root: 'none', expected_contract_version: 'bago.contract.ui.v1' },
    evidence: []
  };
}

describe('capability anatomy contract', () => {
  it('accepts backend read-only snapshots', () => {
    expect(validateCapabilitySnapshot(fixture()).source.authority).toBe('backend');
  });

  it('rejects fixtures as UI authority', () => {
    const value = fixture();
    value.source.authority = 'fixture';
    expect(() => validateCapabilitySnapshot(value)).toThrow(CapabilityContractError);
  });

  it('rejects success without receipt and evidence', () => {
    const value = fixture();
    value.runtime_snapshot.run_state = 'succeeded';
    expect(() => validateCapabilitySnapshot(value)).toThrow(/receipt/);
  });

  it('rejects broken route references', () => {
    const value = fixture();
    value.routes[0].steps[1] = 'missing';
    expect(() => validateCapabilitySnapshot(value)).toThrow(/referencia desconocida/);
  });
});
