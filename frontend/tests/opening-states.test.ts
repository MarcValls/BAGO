import { describe, expect, it } from 'vitest'

import { buildSnapshot } from '../src/app/bootstrapSnapshot'
import { resolveOpeningState } from '../src/features/opening/opening'

function confirmedSnapshot() {
  const snapshot = buildSnapshot({
    status: {
      framework_version: '4.8.1',
      workspace_state_root: 'C:/workspace/.gabo',
      repo_root: 'C:/workspace',
      workspace_state: {
        binding_confirmed: true,
        binding_reason: 'ok',
      },
      provider: 'ollama-local',
      model: 'llama3.2:3b',
      active_bridges: ['ollama-local'],
      health: { ok: true },
    },
    session: { session_id: 'session-1' },
  })

  if (!snapshot) throw new Error('Expected a valid bootstrap snapshot')
  return snapshot
}

describe('critical opening states', () => {
  it('keeps an empty bootstrap blocked while connecting', () => {
    expect(resolveOpeningState(null)).toMatchObject({
      id: 'show_blocked_state',
      targetSection: 'home',
    })
  })

  it('routes an offline backend to Sistema', () => {
    const snapshot = confirmedSnapshot()
    const offline = {
      ...snapshot,
      system: { ...snapshot.system, backendAvailable: false, state: 'error' as const },
    }

    expect(resolveOpeningState(offline)).toMatchObject({
      id: 'show_blocked_state',
      targetSection: 'system',
    })
  })

  it('opens recovery when the runtime is degraded', () => {
    const snapshot = confirmedSnapshot()
    const degraded = {
      ...snapshot,
      system: { ...snapshot.system, state: 'degraded' as const },
    }

    expect(resolveOpeningState(degraded)).toMatchObject({
      id: 'show_recovery',
      targetSection: 'home',
    })
  })

  it('opens recovery when context is stale even with a valid linked session', () => {
    const snapshot = confirmedSnapshot()
    const stale = {
      ...snapshot,
      context: { ...snapshot.context, state: 'stale' as const },
    }

    expect(resolveOpeningState(stale)).toMatchObject({
      id: 'show_recovery',
      targetSection: 'home',
    })
  })

  it('routes a blocked session to workspace repair', () => {
    const snapshot = confirmedSnapshot()
    const blocked = {
      ...snapshot,
      session: { ...snapshot.session, state: 'blocked' as const },
    }

    expect(resolveOpeningState(blocked)).toMatchObject({
      id: 'show_workspace_repair',
      targetSection: 'workspace',
    })
  })
})
