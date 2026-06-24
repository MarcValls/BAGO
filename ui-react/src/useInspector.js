import { useCallback, useEffect, useMemo, useState } from 'react'
import { chatApi } from './api'
import { recordInteraction } from './interactionLog'

const STORAGE_KEY = 'bago.inspector.v1'

function readPersisted() {
  if (typeof window === 'undefined') return null
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

function writePersisted(value) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {}
}

const DEFAULT_EVIDENCE = {
  state: 'PENDIENTE',
  tests: { passed: 0, skipped: 0, failed: 0 },
  subtests: { passed: 0, failed: 0 },
  lastRun: '—',
  duration: '—',
  claims: [],
  notes: [
    'Sin evidencia cargada aún. Ejecuta una verificación para poblar el inspector.',
  ],
}

export function useInspector() {
  const persisted = readPersisted()
  const [open, setOpen] = useState(persisted?.open ?? true)
  const [evidence, setEvidence] = useState(persisted?.evidence || DEFAULT_EVIDENCE)
  const [runtime, setRuntime] = useState(persisted?.runtime || null)
  const [error, setError] = useState('')

  useEffect(() => {
    writePersisted({ open, evidence, runtime })
  }, [open, evidence, runtime])

  const toggle = useCallback((force) => {
    setOpen((current) => (typeof force === 'boolean' ? force : !current))
  }, [])

  const refreshRuntime = useCallback(async () => {
    try {
      const [session, simulation, catalog, rl] = await Promise.all([
        chatApi.getSession().catch(() => null),
        chatApi.getSimulationStatus().catch(() => null),
        chatApi.getCatalogStatus().catch(() => null),
        chatApi.getRlStatus().catch(() => null),
      ])
      setRuntime({ session, simulation, catalog, rl, ts: new Date().toISOString() })
      if (session?.bago_version) {
        setEvidence((current) => ({ ...current, version: session.bago_version }))
      }
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const setClaim = useCallback((index, ok) => {
    setEvidence((current) => ({
      ...current,
      claims: current.claims.map((claim, i) => (i === index ? { ...claim, ok } : claim)),
    }))
    recordInteraction('claim-toggle', { index, ok })
  }, [])

  const addClaim = useCallback((text) => {
    if (!text || !text.trim()) return
    setEvidence((current) => ({
      ...current,
      claims: [...current.claims, { text: text.trim(), proof: 'manual', ok: true }],
    }))
  }, [])

  const summary = useMemo(() => {
    const claimsOk = evidence.claims.filter((c) => c.ok).length
    return {
      state: evidence.state,
      claimsOk,
      claimsTotal: evidence.claims.length,
      testsPassed: evidence.tests?.passed || 0,
      testsFailed: evidence.tests?.failed || 0,
    }
  }, [evidence])

  return {
    open,
    toggle,
    evidence,
    setEvidence,
    setClaim,
    addClaim,
    runtime,
    refreshRuntime,
    error,
    summary,
  }
}
