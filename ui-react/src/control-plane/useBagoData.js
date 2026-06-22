import { useCallback, useEffect, useRef, useState } from 'react'

function getElectron() {
  return typeof window !== 'undefined' ? window.bagoElectron : null
}

/**
 * Envuelve un fetcher de Electron para que, si no hay bridge (modo web/dev),
 * devuelva un fallback en lugar de lanzar un error. Así `npm run dev` y
 * `npm run preview` siguen usables aunque las vistas de datos reales estén vacías.
 */
function withElectronFallback(fetcher, fallback) {
  return async () => {
    const e = getElectron()
    if (!e) return fallback
    return fetcher(e)
  }
}

/**
 * Hook que combina polling + evento push para refresco solo-cambio.
 * @param {Function} fn - función async que obtiene los datos
 * @param {Array} deps - dependencias
 * @param {number} intervalMs - polling de respaldo (0 = sin polling)
 * @param {string|null} eventScope - si coincide con el scope del evento 'bago:data-changed', refresca al instante
 */
export function useAsync(fn, deps = [], intervalMs = 0, eventScope = null) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const lastJsonRef = useRef(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const run = useCallback(() => {
    let active = true
    setLoading(true)
    setError(null)
    Promise.resolve()
      .then(() => fnRef.current())
      .then((result) => {
        if (!active) return
        const json = JSON.stringify(result)
        if (json !== lastJsonRef.current) {
          lastJsonRef.current = json
          setData(result)
        }
        setLoading(false)
      })
      .catch((err) => {
        if (!active) return
        setError(err?.message || String(err))
        setLoading(false)
      })
    return () => { active = false }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const cancel = run()
    let timer = null
    if (intervalMs > 0) {
      timer = setInterval(() => run(), intervalMs)
    }
    return () => { cancel(); if (timer) clearInterval(timer) }
  }, [run]) // eslint-disable-line react-hooks/exhaustive-deps

  // Suscripción a evento push 'bago:data-changed'
  useEffect(() => {
    if (!eventScope) return
    const e = getElectron()
    if (!e?.onDataChanged) return
    e.onDataChanged((scope) => {
      if (scope === eventScope) run()
    })
  }, [eventScope, run])

  return { data, loading, error, refresh: run }
}

/** Instalaciones reales del filesystem — push event + polling respaldo 30s */
export function useInstallations() {
  return useAsync(
    withElectronFallback((e) => e.scanInstallations(), { installations: [], summary: {} }),
    [],
    30000,
    'installations'
  )
}

/** Releases reales desde GitHub — push event + polling respaldo 120s */
export function useReleases() {
  return useAsync(
    withElectronFallback((e) => e.fetchReleases(), []),
    [],
    120000,
    'releases'
  )
}

/** Health real del manager — push event + polling respaldo 30s */
export function useManagerHealth() {
  return useAsync(
    withElectronFallback((e) => e.managerHealth(), { checks: [] }),
    [],
    30000,
    'health'
  )
}

/** Jobs de release reales — push event + polling respaldo 15s */
export function useReleaseJobs() {
  return useAsync(
    withElectronFallback((e) => e.listReleaseJobs(), []),
    [],
    15000,
    'jobs'
  )
}

/** Event ledger real — push event + polling respaldo 30s */
export function useEventLedger(limit = 60) {
  return useAsync(
    withElectronFallback((e) => e.eventLedger(limit), []),
    [limit],
    30000,
    'audit'
  )
}

/** Node status real — push event + polling respaldo 30s */
export function useNodeStatus() {
  return useAsync(
    withElectronFallback((e) => e.runNodeStatus(), {}),
    [],
    30000,
    'nodes'
  )
}

/** Node matrix real — push event + polling respaldo 30s */
export function useNodeMatrix() {
  return useAsync(
    withElectronFallback((e) => e.runNodeMatrix(), {}),
    [],
    30000,
    'nodes'
  )
}

/** Node pieces reales — push event + polling respaldo 30s */
export function useNodePieces() {
  return useAsync(
    withElectronFallback((e) => e.runNodePieces(), { pieces: [] }),
    [],
    30000,
    'nodes'
  )
}

/** Node connectors reales — push event + polling respaldo 30s */
export function useNodeConnectors() {
  return useAsync(
    withElectronFallback((e) => e.runNodeConnectors(), { connectors: [] }),
    [],
    30000,
    'nodes'
  )
}

/** Node evidence real — push event + polling respaldo 30s */
export function useNodeEvidence(limit = 40) {
  return useAsync(
    withElectronFallback((e) => e.runNodeEvidence(limit), { evidence: [] }),
    [limit],
    30000,
    'nodes'
  )
}

/** Project audit real (IPC bago:project-audit) */
export function useProjectAudit() {
  return useAsync(
    withElectronFallback((e) => e.projectAudit(), { findings: [] }),
    []
  )
}

/** Bago audit real (IPC bago:bago-audit) */
export function useBagoAudit() {
  return useAsync(
    withElectronFallback((e) => e.bagoAudit(), { findings: [] }),
    []
  )
}

/** Hook para suscribirse a eventos IPC push de Electron */
export function useBagoEvent(eventName, callback) {
  const cbRef = useRef(callback)
  cbRef.current = callback
  useEffect(() => {
    const e = getElectron()
    if (!e || !e[eventName]) return
    e[eventName]((...args) => cbRef.current?.(...args))
  }, [eventName])
}

/** Release job change subscription */
export function useReleaseJobChanges() {
  const [job, setJob] = useState(null)
  useEffect(() => {
    const e = getElectron()
    if (!e) return
    e.onReleaseJobChanged?.((j) => setJob(j))
  }, [])
  return job
}
