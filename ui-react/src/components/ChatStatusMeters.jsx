import { useEffect, useState } from 'react'
import { chatApi } from '../api'

function Meter({ label, value, max, unit, color }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  const barColor = color || (pct > 60 ? '#4ade80' : pct > 25 ? '#fbbf24' : '#f87171')

  return (
    <div className="status-meter" title={`${label}: ${value}${unit} / ${max}${unit}`}>
      <div className="status-meter-label">{label}</div>
      <div className="status-meter-track">
        <div
          className="status-meter-fill"
          style={{ width: `${pct}%`, background: barColor }}
        />
      </div>
      <div className="status-meter-value">{value}{unit}</div>
    </div>
  )
}

export default function ChatStatusMeters({ session, busy }) {
  const [providers, setProviders] = useState(null)
  const [rlStatus, setRlStatus] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function poll() {
      try {
        const [p, rl] = await Promise.all([
          chatApi.listProviders().catch(() => null),
          chatApi.getRlStatus().catch(() => null),
        ])
        if (!active) return
        setProviders(p)
        setRlStatus(rl)
        setError('')
      } catch (err) {
        if (!active) return
        setError(err.message)
      }
    }

    poll()
    const timer = setInterval(poll, 8000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const providerCount = providers?.providers?.length || 0
  const activeProvider = session?.provider || '—'
  const activeModel = session?.model || '—'

  const rlTokens = rlStatus?.can_execute != null
    ? (rlStatus?.can_execute ? 5 : 0)
    : 0
  const rlMax = 5

  const uptimeS = session?.uptime_s || session?.uptime || 0
  const uptimeMax = 300

  const modelOk = activeModel !== '—' ? 1 : 0
  const modelMax = 1

  return (
    <div className="chat-status-meters" role="region" aria-label="Salud del sistema">
      <div className="status-meters-header">
        <span className="status-meters-title">HP</span>
        {busy && <span className="status-meters-busty">● activo</span>}
      </div>
      <div className="status-meters-grid">
        <Meter label="Provider" value={providerCount} max={Math.max(providerCount, 1)} unit="" color="#60a5fa" />
        <Meter label="Modelo" value={modelOk} max={modelMax} unit="" color={modelOk ? '#4ade80' : '#f87171'} />
        <Meter label="Rate" value={rlTokens} max={rlMax} unit="" color={rlTokens > 2 ? '#4ade80' : rlTokens > 0 ? '#fbbf24' : '#f87171'} />
        <Meter label="Uptime" value={Math.round(uptimeS)} max={uptimeMax} unit="s" color="#a78bfa" />
      </div>
      {error && <div className="status-meters-error">{error}</div>}
    </div>
  )
}