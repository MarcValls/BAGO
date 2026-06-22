import { useCallback, useEffect, useMemo, useState } from 'react'
import { chatApi } from './api'
import { recordInteraction } from './interactionLog'
import { DEFAULT_VERSION_LABEL } from './version'

const DEFAULT_KIT = {
  installation: { id: 'local', label: 'BAGO local', version: DEFAULT_VERSION_LABEL, status: 'ready' },
  model: { id: 'llama3.2:3b', label: 'llama3.2:3b', provider: 'ollama' },
  pipeline: { id: 'code-forge-3b', label: 'Code Forge', variant: 'staged' },
  policy: { id: 'staged', label: 'Staged', risk: 'bajo' },
  pieces: { count: 0, label: '0 piezas' },
  simulation: { mode: 'off' },
  catalog: { mode: 'off' },
}

const STORAGE_KEY = 'bago.session-kit.v1'

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

export function useSessionKit() {
  const [kit, setKit] = useState(() => ({ ...DEFAULT_KIT, ...(readPersisted() || {}) }))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    writePersisted(kit)
  }, [kit])

  const update = useCallback((patch, source = 'local') => {
    recordInteraction('kit-update', { source, patch })
    setKit((current) => ({ ...current, ...patch }))
  }, [])

  const setInstallation = useCallback((installation) => {
    update({ installation }, 'set-installation')
  }, [update])

  const setModel = useCallback((model, provider) => {
    update({ model: { ...(model && typeof model === 'object' ? model : { id: model }), provider: provider || 'ollama' } }, 'set-model')
  }, [update])

  const setPipeline = useCallback((pipeline) => {
    update({ pipeline }, 'set-pipeline')
  }, [update])

  const setPolicy = useCallback((policy) => {
    update({ policy }, 'set-policy')
  }, [update])

  const setSimulation = useCallback((mode) => {
    update({ simulation: { mode } }, 'set-simulation')
  }, [update])

  const setCatalog = useCallback((mode) => {
    update({ catalog: { mode } }, 'set-catalog')
  }, [update])

  const refreshFromBackend = useCallback(async () => {
    setBusy(true)
    try {
      const [session, simulation, catalog] = await Promise.all([
        chatApi.getSession(),
        chatApi.getSimulationStatus().catch(() => null),
        chatApi.getCatalogStatus().catch(() => null),
      ])
      const next = { ...kit }
      if (session?.provider) {
        next.model = { id: session.model || 'llama3.2:3b', provider: session.provider }
        next.installation = {
          ...(next.installation || DEFAULT_KIT.installation),
          version: session.bago_version || next.installation?.version || DEFAULT_VERSION_LABEL,
        }
      }
      if (simulation?.mode) next.simulation = { mode: simulation.mode }
      if (catalog?.mode) next.catalog = { mode: catalog.mode }
      setKit(next)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }, [kit])

  const summary = useMemo(() => {
    const pieces = kit.pieces?.count ?? 0
    return {
      installationLabel: kit.installation?.label || 'BAGO local',
      modelLabel: kit.model?.label || kit.model?.id || 'sin modelo',
      pipelineLabel: `${kit.pipeline?.label || 'Code Forge'} · ${kit.pipeline?.variant || 'staged'}`,
      piecesLabel: `${pieces} piezas`,
      policyLabel: kit.policy?.label || 'Staged',
      simulationLabel: `simulación: ${kit.simulation?.mode || 'off'}`,
      catalogLabel: `catálogo: ${kit.catalog?.mode || 'off'}`,
    }
  }, [kit])

  return {
    kit,
    busy,
    error,
    summary,
    update,
    setInstallation,
    setModel,
    setPipeline,
    setPolicy,
    setSimulation,
    setCatalog,
    refreshFromBackend,
  }
}
