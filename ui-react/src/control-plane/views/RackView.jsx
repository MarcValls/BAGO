import { useMemo, useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { DEMO_RACK_CHAIN, RACK_MODULE_TYPES } from '../rpg-data'

const STATUS = { idle: 'idle', running: 'running', ok: 'ok', error: 'error' }
const STATUS_ICONS = { idle: '○', running: '◐', ok: '✓', error: '✕' }

function RackModule({ mod, status, onClick, active }) {
  const meta = RACK_MODULE_TYPES[mod.type] || RACK_MODULE_TYPES.input
  return (
    <button
      type="button"
      className={`cp-rack-module ${active ? 'is-active' : ''} status-${status}`}
      style={{ borderColor: meta.color }}
      onClick={onClick}
    >
      <div className="cp-rack-module-top">
        <span className="cp-rack-module-type" style={{ color: meta.color }}>{meta.label}</span>
        <span className="cp-rack-module-status">{STATUS_ICONS[status]}</span>
      </div>
      <div className="cp-rack-module-label">{mod.label}</div>
      <div className="cp-rack-module-cmd">{mod.command}</div>
      <div className="cp-rack-module-ports">
        <div className="cp-rack-port cp-rack-port-in" />
        <div className="cp-rack-port cp-rack-port-out" />
      </div>
    </button>
  )
}

export default function RackView({ context, onAction }) {
  const [chain, setChain] = useState(DEMO_RACK_CHAIN)
  const [statuses, setStatuses] = useState({})
  const [outputs, setOutputs] = useState({})
  const [isRunning, setIsRunning] = useState(false)
  const [selected, setSelected] = useState(null)

  const dependents = useMemo(() => {
    const map = new Map(chain.map((m) => [m.id, []]))
    chain.forEach((m) => {
      m.dependsOn?.forEach((dep) => {
        map.get(dep)?.push(m.id)
      })
    })
    return map
  }, [chain])

  async function simulateRun(mod) {
    const ms = 400 + Math.floor(Math.random() * 1000)
    await new Promise((r) => setTimeout(r, ms))
    if (Math.random() < 0.05) throw new Error('fallo simulado')
    return { duration: ms }
  }

  async function runChain() {
    if (isRunning) return
    setIsRunning(true)
    setStatuses(Object.fromEntries(chain.map((m) => [m.id, STATUS.idle])))
    setOutputs({})
    onAction?.('toast', 'Rack iniciado')

    let current = {}
    const pending = [...chain]
    const running = new Set()

    while (pending.length > 0) {
      const ready = pending.filter((m) => {
        if (current[m.id]) return false
        if (!m.dependsOn?.length) return true
        return m.dependsOn.every((d) => current[d] === STATUS.ok)
      })

      if (ready.length === 0) {
        await new Promise((r) => setTimeout(r, 100))
        continue
      }

      const batch = ready.slice(0, 2)
      batch.forEach((m) => {
        running.add(m.id)
        setStatuses((s) => ({ ...s, [m.id]: STATUS.running }))
      })

      await Promise.all(
        batch.map(async (m) => {
          try {
            const res = await simulateRun(m)
            current[m.id] = STATUS.ok
            setStatuses((s) => ({ ...s, [m.id]: STATUS.ok }))
            setOutputs((o) => ({
              ...o,
              [m.id]: `$ ${m.command}\n✓ completado en ${res.duration}ms`,
            }))
          } catch (err) {
            current[m.id] = STATUS.error
            setStatuses((s) => ({ ...s, [m.id]: STATUS.error }))
            setOutputs((o) => ({ ...o, [m.id]: `$ ${m.command}\n✕ ${err.message}` }))
            dependents.get(m.id)?.forEach((depId) => {
              current[depId] = STATUS.error
              setStatuses((s) => ({ ...s, [depId]: STATUS.error }))
            })
          } finally {
            running.delete(m.id)
          }
        })
      )

      pending.splice(
        0,
        pending.length,
        ...pending.filter((m) => current[m.id] !== STATUS.ok && current[m.id] !== STATUS.error)
      )
    }

    setIsRunning(false)
    const failed = chain.some((m) => current[m.id] === STATUS.error)
    onAction?.('toast', failed ? 'Rack terminado con errores' : 'Rack completado')
  }

  function resetChain() {
    setStatuses({})
    setOutputs({})
    setIsRunning(false)
    onAction?.('toast', 'Rack reiniciado')
  }

  function moveModule(id, direction) {
    const idx = chain.findIndex((m) => m.id === id)
    if (idx < 0) return
    const nextIdx = idx + direction
    if (nextIdx < 0 || nextIdx >= chain.length) return
    const next = [...chain]
    ;[next[idx], next[nextIdx]] = [next[nextIdx], next[idx]]
    setChain(next)
  }

  const progress = useMemo(() => {
    const done = chain.filter((m) => statuses[m.id] === STATUS.ok).length
    return { done, total: chain.length }
  }, [statuses, chain])

  return (
    <section className="cp-view cp-view-active cp-rack-view">
      <div className="cp-toolbar">
        <div className="cp-rack-title">
          <Icon name="grid" size={20} />
          <div>
            <div>Rack de ejecución</div>
            <div className="cp-rack-subtitle">Cadena de módulos · {progress.done}/{progress.total}</div>
          </div>
        </div>
        <div className="cp-rack-controls">
          <button type="button" className="cp-btn cp-btn-primary" onClick={runChain} disabled={isRunning}>
            {isRunning ? 'Ejecutando…' : '▶ Ejecutar rack'}
          </button>
          <button type="button" className="cp-btn" onClick={resetChain} disabled={isRunning}>
            Reiniciar
          </button>
        </div>
      </div>

      <div className="cp-rack-body">
        <div className="cp-rack-rail">
          {chain.map((mod, idx) => (
            <div key={mod.id} className="cp-rack-unit">
              <RackModule
                mod={mod}
                status={statuses[mod.id] || STATUS.idle}
                active={selected?.id === mod.id}
                onClick={() => setSelected(mod)}
              />
              <div className="cp-rack-arrows">
                <button type="button" disabled={idx === 0} onClick={() => moveModule(mod.id, -1)}>‹</button>
                <button type="button" disabled={idx === chain.length - 1} onClick={() => moveModule(mod.id, 1)}>›</button>
              </div>
            </div>
          ))}
        </div>

        {selected && (
          <div className="cp-rack-detail">
            <div className="cp-rack-detail-head">
              <span>{selected.label}</span>
              <button type="button" onClick={() => setSelected(null)}>✕</button>
            </div>
            <div className="cp-rack-detail-body">
              <Badge>{RACK_MODULE_TYPES[selected.type]?.label || selected.type}</Badge>
              <div className="cp-rack-detail-cmd">{selected.command}</div>
              {selected.dependsOn?.length > 0 && (
                <div className="cp-rack-detail-deps">
                  Depende de: {selected.dependsOn.join(', ')}
                </div>
              )}
              {outputs[selected.id] && (
                <pre className="cp-rack-detail-output">{outputs[selected.id]}</pre>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
