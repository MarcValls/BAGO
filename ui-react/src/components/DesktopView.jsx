import { useEffect, useState } from 'react'
import ComposeBar from './ComposeBar'

function StatusCard({ title, value, note }) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      <div className="card-value">{value}</div>
      {note ? <div className="card-note">{note}</div> : null}
    </div>
  )
}

function formatPayload(value) {
  if (!value) return ''
  return JSON.stringify(value, null, 2)
}

export default function DesktopView({ control }) {
  const latestCommand = control.commandLog[0]
  const recentEvents = [...control.events].reverse().slice(0, 6)
  const [credentialProvider, setCredentialProvider] = useState(control.session?.provider || '')
  const [credentialKey, setCredentialKey] = useState('')
  const [credentialValue, setCredentialValue] = useState('')

  useEffect(() => {
    if (control.session?.provider) {
      setCredentialProvider(control.session.provider)
    }
  }, [control.session?.provider])

  function syncCredentialProvider(nextProvider) {
    setCredentialProvider(nextProvider)
  }

  function saveCredential(event) {
    event.preventDefault()
    const provider = credentialProvider.trim()
    const key = credentialKey.trim()
    const value = credentialValue.trim()
    if (!provider || !key || !value) return
    control.submit(`/credentials set ${provider} ${key} ${value}`, 'desktop')
    setCredentialKey('')
    setCredentialValue('')
  }

  return (
    <section className="desktop-shell">
      <div className="desktop-grid">
        <div className="panel">
          <h3>Sesión</h3>
          <div className="cards">
            <StatusCard title="Provider" value={control.session?.provider || '-'} />
            <StatusCard title="Modelo" value={control.session?.model || '-'} />
            <StatusCard title="Catálogo" value={control.catalog?.mode || '-'} note="all o available-only" />
            <StatusCard
              title="Simulación"
              value={control.simulation?.mode || '-'}
              note={`${control.simulation?.events_logged || 0} eventos · ${control.simulation?.authority || 'observer-only'}`}
            />
            <StatusCard
              title="RL bridge"
              value={control.rl?.mode || '-'}
              note={`ejecuta acciones: ${control.rl?.can_execute ? 'sí' : 'no'} · externo: ${control.rl?.external_rl?.available ? 'ok' : 'no'}`}
            />
          </div>
          <div className="button-row">
            <button onClick={() => control.submit('/status', 'desktop')} disabled={control.busy}>/status</button>
            <button onClick={() => control.submit('/providers', 'desktop')} disabled={control.busy}>/providers</button>
            <button onClick={() => control.submit('/session', 'desktop')} disabled={control.busy}>/session</button>
            <button onClick={() => control.submit('/tools enable', 'desktop')} disabled={control.busy}>/tools enable</button>
            <button onClick={() => control.submit('/credentials list', 'desktop')} disabled={control.busy}>/credentials list</button>
            <button onClick={() => control.setRlShadow(true)} disabled={control.busy}>RL shadow on</button>
            <button onClick={() => control.setRlShadow(false)} disabled={control.busy}>RL off</button>
          </div>
          <form className="credentials-form" onSubmit={saveCredential}>
            <div className="credentials-form-head">
              <h4>Credenciales</h4>
              <span>Se guardan en `.bago/credentials.json`.</span>
            </div>
            <div className="credentials-grid">
              <label>
                Provider
                <select value={credentialProvider} onChange={(event) => syncCredentialProvider(event.target.value)} disabled={control.busy}>
                  <option value="">Elegir provider</option>
                  {control.providers.map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Key
                <input
                  value={credentialKey}
                  onChange={(event) => setCredentialKey(event.target.value)}
                  placeholder="OPENAI_API_KEY"
                  disabled={control.busy}
                />
              </label>
            </div>
            <label className="credentials-value">
              Valor
              <input
                value={credentialValue}
                onChange={(event) => setCredentialValue(event.target.value)}
                placeholder="sk-..."
                disabled={control.busy}
              />
            </label>
            <div className="credentials-actions">
              <button type="submit" disabled={control.busy || !credentialProvider || !credentialKey || !credentialValue}>
                Guardar credencial
              </button>
              <button type="button" onClick={() => control.submit('/credentials list', 'desktop')} disabled={control.busy}>
                Ver credenciales
              </button>
            </div>
          </form>
        </div>

        <div className="panel">
          <h3>Providers</h3>
          <ul className="provider-list">
            {control.providers.map((provider) => (
              <li key={provider.name} className={provider.active ? 'active' : ''}>
                <div>
                  <strong>{provider.name}</strong>
                  <span>{provider.models.length} modelos · {provider.configured ? 'configurado' : 'sin configurar'}</span>
                </div>
                <button
                  onClick={() => control.switchProviderModel(provider.name, '', 'desktop')}
                  disabled={control.busy || !provider.configured || provider.active}
                >
                  {provider.active ? 'Activo' : 'Activar'}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel">
          <h3>Modelos visibles</h3>
          <div className="panel-note">Provider activo: {control.session?.provider || '-'}</div>
          <ul className="model-list">
            {control.models.map((model) => (
              <li key={model.id}>
                <div>
                  <strong>{model.id}</strong>
                  <span>{model.available ? 'disponible' : 'cerrado por disponibilidad'}</span>
                </div>
                <button
                  onClick={() => control.switchProviderModel(control.session?.provider, model.id, 'desktop')}
                  disabled={control.busy || !control.session?.provider || !model.available || control.session?.model === model.id}
                >
                  {control.session?.model === model.id ? 'Activo' : 'Usar'}
                </button>
              </li>
            ))}
            {!control.models.length ? <li className="empty-state">No hay modelos cargados.</li> : null}
          </ul>
        </div>
      </div>

      <div className="desktop-secondary-grid">
        <div className="panel">
          <h3>Resultado estructurado</h3>
          {latestCommand ? (
            <div className="command-entry">
              <div className="command-entry-header">
                <strong>{latestCommand.command}</strong>
                <span>{latestCommand.channel}</span>
              </div>
              <div className="command-entry-message">{latestCommand.response?.message || '(sin mensaje)'}</div>
              {latestCommand.response?.data ? (
                <pre className="data-block">{formatPayload(latestCommand.response.data)}</pre>
              ) : null}
              {latestCommand.response?.plan ? (
                <pre className="data-block">{formatPayload(latestCommand.response.plan)}</pre>
              ) : null}
            </div>
          ) : (
            <div className="empty-state">Todavía no hay resultados de comandos.</div>
          )}
        </div>

        <div className="panel">
          <h3>Eventos shadow</h3>
          <div className="panel-note">{control.simulation?.mode_note}</div>
          <div className="event-list">
            {recentEvents.map((event) => (
              <div key={event.id} className="event-row">
                <div className="event-head">
                  <strong>{event.action_kind}</strong>
                  <span>{event.channel} · reward {event.reward}</span>
                </div>
                <div className="event-note">
                  recomendado: {event.recommended?.provider ? `${event.recommended.provider}/${event.recommended.model}` : event.recommended?.command || event.recommended?.kind}
                </div>
              </div>
            ))}
            {!recentEvents.length ? <div className="empty-state">Sin eventos todavía.</div> : null}
          </div>
        </div>
      </div>

      <div className="panel history-panel">
        <h3>Historial</h3>
        <div className="history-list">
          {control.history.map((item, index) => (
            <div key={`${item.role}-${index}`} className={`history-row role-${item.role}`}>
              <span className="role-pill">{item.role}</span>
              <span>{item.content}</span>
            </div>
          ))}
          {!control.history.length ? <div className="empty-state">Sin mensajes todavía.</div> : null}
        </div>
        <ComposeBar
          busy={control.busy}
          onSubmit={(value) => control.submit(value, 'desktop')}
          placeholder="Mensaje o comando visual"
        />
      </div>
    </section>
  )
}
