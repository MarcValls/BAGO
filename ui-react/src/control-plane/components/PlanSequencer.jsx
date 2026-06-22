import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CPIcons } from '../icons'
import { PLANS, computePlanSteps } from '../planData'

const STATUS = {
  idle: 'idle',
  queued: 'queued',
  running: 'running',
  ok: 'ok',
  error: 'error',
}

const STATUS_ICONS = {
  idle: '○',
  queued: '◌',
  running: '◐',
  ok: '✓',
  error: '✕',
}

function classFor(status) {
  return `cp-step-status cp-step-status-${status}`
}

function simulateRun(command) {
  const ms = 600 + Math.floor(Math.random() * 1400)
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < 0.05) {
        reject(new Error(`Command failed: ${command}`))
      } else {
        resolve({ command, duration: ms })
      }
    }, ms)
  })
}

export default function PlanSequencer({ onClose, onToast }) {
  const [selectedPlanId, setSelectedPlanId] = useState(PLANS[0].id)
  const [statuses, setStatuses] = useState({})
  const [outputs, setOutputs] = useState({})
  const [isRunning, setIsRunning] = useState(false)
  const [showOutputFor, setShowOutputFor] = useState(null)
  const abortRef = useRef(false)

  const plan = useMemo(
    () => PLANS.find((p) => p.id === selectedPlanId),
    [selectedPlanId]
  )

  const { dependents } = useMemo(
    () => computePlanSteps(plan.steps),
    [plan]
  )

  const readySteps = useCallback(
    (currentStatuses) => {
      return plan.steps.filter((s) => {
        if (currentStatuses[s.id] && currentStatuses[s.id] !== STATUS.idle) return false
        if (!s.dependsOn) return true
        return s.dependsOn.every((dep) => currentStatuses[dep] === STATUS.ok)
      })
    },
    [plan]
  )

  const reset = () => {
    setStatuses({})
    setOutputs({})
    setIsRunning(false)
    abortRef.current = false
  }

  useEffect(() => {
    reset()
  }, [selectedPlanId])

  const runAll = useCallback(async () => {
    if (isRunning) return
    abortRef.current = false
    setIsRunning(true)
    onToast?.(`Plan "${plan.label}" iniciado`)

    let currentStatuses = {}
    let pending = [...plan.steps]
    setStatuses(Object.fromEntries(plan.steps.map((s) => [s.id, STATUS.idle])))

    const runStep = async (step) => {
      if (abortRef.current) return { skipped: true }
      setStatuses((prev) => ({ ...prev, [step.id]: STATUS.running }))
      try {
        const result = await simulateRun(step.command)
        if (abortRef.current) return { skipped: true }
        setStatuses((prev) => ({ ...prev, [step.id]: STATUS.ok }))
        setOutputs((prev) => ({
          ...prev,
          [step.id]: `$ ${step.command}\n✓ completado en ${result.duration}ms`,
        }))
        return { ok: true }
      } catch (err) {
        setStatuses((prev) => ({ ...prev, [step.id]: STATUS.error }))
        setOutputs((prev) => ({
          ...prev,
          [step.id]: `$ ${step.command}\n✕ ${err.message}`,
        }))
        return { error: true }
      }
    }

    while (pending.length > 0 && !abortRef.current) {
      const nextBatch = readySteps(currentStatuses)
      if (nextBatch.length === 0) {
        if (pending.some((s) => currentStatuses[s.id] === STATUS.error)) break
        await new Promise((r) => setTimeout(r, 100))
        continue
      }

      const batch = nextBatch.filter((s) => currentStatuses[s.id] === STATUS.idle)
      if (batch.length === 0) {
        await new Promise((r) => setTimeout(r, 100))
        continue
      }

      setStatuses((prev) => {
        const next = { ...prev }
        batch.forEach((s) => (next[s.id] = STATUS.queued))
        return next
      })

      await Promise.all(
        batch.map(async (step) => {
          const result = await runStep(step)
          if (result.error) {
            dependents.get(step.id).forEach((depId) => {
              currentStatuses[depId] = STATUS.idle
            })
          }
        })
      )

      currentStatuses = { ...currentStatuses }
      pending = pending.filter((s) => currentStatuses[s.id] !== STATUS.ok && currentStatuses[s.id] !== STATUS.error)
    }

    setIsRunning(false)
    const failed = plan.steps.some((s) => currentStatuses[s.id] === STATUS.error)
    onToast?.(failed ? `Plan "${plan.label}" terminado con errores` : `Plan "${plan.label}" completado`)
  }, [plan, readySteps, isRunning, onToast, dependents])

  const abort = () => {
    abortRef.current = true
    setIsRunning(false)
    onToast?.('Plan detenido')
  }

  const progress = useMemo(() => {
    const done = plan.steps.filter((s) => statuses[s.id] === STATUS.ok).length
    return { done, total: plan.steps.length }
  }, [statuses, plan])

  return (
    <div className="cp-plan-overlay" onClick={onClose}>
      <div className="cp-plan" onClick={(e) => e.stopPropagation()}>
        <div className="cp-plan-head">
          <div className="cp-plan-title">
            <span className="cp-icon" style={{ width: 20, height: 20 }}>{CPIcons.scripts}</span>
            Ejecutar plan
          </div>
          <button type="button" className="cp-plan-close" onClick={onClose}>✕</button>
        </div>

        <div className="cp-plan-body">
          <div className="cp-plan-select-row">
            <select
              value={selectedPlanId}
              onChange={(e) => setSelectedPlanId(e.target.value)}
              disabled={isRunning}
            >
              {PLANS.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <button
              type="button"
              className="cp-btn cp-btn-primary"
              onClick={runAll}
              disabled={isRunning}
            >
              {isRunning ? 'Ejecutando…' : 'Ejecutar plan'}
            </button>
            {isRunning ? (
              <button type="button" className="cp-btn cp-btn-danger" onClick={abort}>
                Detener
              </button>
            ) : (
              <button type="button" className="cp-btn" onClick={reset} disabled={progress.done === 0}>
                Reiniciar
              </button>
            )}
          </div>

          <div className="cp-plan-desc">{plan.description}</div>

          <div className="cp-plan-progress">
            <div
              className="cp-plan-progress-bar"
              style={{ width: `${(progress.done / progress.total) * 100}%` }}
            />
            <span className="cp-plan-progress-text">{progress.done}/{progress.total}</span>
          </div>

          <div className="cp-steps">
            {plan.steps.map((step) => {
              const status = statuses[step.id] || STATUS.idle
              const expanded = showOutputFor === step.id
              return (
                <div
                  key={step.id}
                  className={`cp-step ${status === STATUS.running ? 'is-running' : ''} ${status === STATUS.ok ? 'is-ok' : ''} ${status === STATUS.error ? 'is-error' : ''}`}
                >
                  <button
                    type="button"
                    className="cp-step-row"
                    onClick={() => setShowOutputFor(expanded ? null : step.id)}
                  >
                    <span className={classFor(status)}>{STATUS_ICONS[status]}</span>
                    <span className="cp-step-label">{step.label}</span>
                    {step.dependsOn && step.dependsOn.length > 0 ? (
                      <span className="cp-step-meta" title={`Dep. de ${step.dependsOn.join(', ')}`}>
                        ⟁ {step.dependsOn.length}
                      </span>
                    ) : null}
                    <span className="cp-step-cmd">{step.command}</span>
                    {outputs[step.id] ? (
                      <span className="cp-step-toggle">{expanded ? '▾' : '▸'}</span>
                    ) : null}
                  </button>
                  {expanded && outputs[step.id] ? (
                    <pre className="cp-step-output">{outputs[step.id]}</pre>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
