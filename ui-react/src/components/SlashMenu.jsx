import { useEffect, useMemo, useState } from 'react'

function compact(text, limit = 72) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  if (value.length <= limit) return value
  return `${value.slice(0, limit - 1).trim()}…`
}

function runCommand(control, command, confirmMessage = '') {
  if (confirmMessage && !window.confirm(confirmMessage)) return
  void control.submit(command, control.mode)
}

function Button({ label, command, control, disabled, confirmMessage = '', title, tone = 'default' }) {
  return (
    <button
      type="button"
      className={`menu-chip tone-${tone}`}
      title={title || command}
      disabled={disabled}
      onClick={() => runCommand(control, command, confirmMessage)}
    >
      {label}
    </button>
  )
}

function Section({ title, description, meta, children }) {
  return (
    <section className="menu-section">
      <header className="menu-section-head">
        <div>
          <h3>{title}</h3>
          <p>{description}</p>
        </div>
        {meta ? <span className="menu-section-meta">{meta}</span> : null}
      </header>
      {children}
    </section>
  )
}

export default function SlashMenu({ control, menu }) {
  const [credentialProvider, setCredentialProvider] = useState('')
  const [credentialKey, setCredentialKey] = useState('')
  const [credentialValue, setCredentialValue] = useState('')

  const config = menu?.config || {}
  const credentialsSchema = menu?.credentials_schema || {}
  const credentials = menu?.credentials || {}
  const sessions = menu?.sessions || []
  const agents = menu?.agents || []
  const tools = menu?.tools || []
  const scripts = menu?.scripts || []
  const memories = menu?.knowledge_recent || []

  const userPrompts = useMemo(() => {
    return [...control.history]
      .filter((item) => item.role === 'user' && !String(item.content || '').trim().startsWith('/'))
      .slice(-6)
      .reverse()
  }, [control.history])

  const recentHistory = useMemo(() => {
    return [...control.history].slice(-5).reverse()
  }, [control.history])

  const schemaProviders = useMemo(() => {
    return Object.keys(credentialsSchema).sort()
  }, [credentialsSchema])

  useEffect(() => {
    if (!schemaProviders.length) {
      setCredentialProvider('')
      return
    }
    if (!credentialProvider || !credentialsSchema[credentialProvider]) {
      const preferred = credentialsSchema[control.session?.provider]
        ? control.session?.provider
        : schemaProviders[0]
      setCredentialProvider(preferred || '')
    }
  }, [control.session?.provider, credentialProvider, credentialsSchema, schemaProviders])

  useEffect(() => {
    const keys = Object.keys(credentialsSchema[credentialProvider] || {})
    if (!keys.length) {
      setCredentialKey('')
      return
    }
    if (!keys.includes(credentialKey)) {
      setCredentialKey(keys[0])
    }
  }, [credentialKey, credentialProvider, credentialsSchema])

  const selectedProviderModels = useMemo(() => {
    const active = control.providers.find((provider) => provider.name === control.session?.provider)
    return active?.models || control.models || []
  }, [control.models, control.providers, control.session?.provider])

  const canSaveCredential = credentialProvider && credentialKey && credentialValue.trim()

  function saveCredential(event) {
    event.preventDefault()
    if (!canSaveCredential) return
    runCommand(
      control,
      `/credentials set ${credentialProvider} ${credentialKey} ${credentialValue.trim()}`,
    )
    setCredentialValue('')
  }

  function toggleConfig(key, nextValue) {
    runCommand(control, `/config set ${key} ${String(nextValue)}`)
  }

  return (
    <section className="menu-shell">
      <header className="menu-top">
        <div>
          <h2>Menú /</h2>
          <p>Navegación completa por categorías, submenús y acciones directas.</p>
        </div>
        <div className="menu-top-meta">
          <span>{sessions.length} sesiones</span>
          <span>{agents.length} agentes</span>
          <span>{memories.length} recuerdos</span>
        </div>
      </header>

      <div className="menu-grid">
        <Section
          title="Sesión y estado"
          description="Guardar, cargar, revisar y marcar contexto sin escribir comandos."
          meta="session-first"
        >
          <div className="chip-row">
            <Button label="/status" command="/status" control={control} disabled={control.busy} />
            <Button label="/session" command="/session" control={control} disabled={control.busy} />
            <Button label="/save" command="/save" control={control} disabled={control.busy} />
            <Button label="/help" command="/help" control={control} disabled={control.busy} />
            <Button label="/quit" command="/quit" control={control} disabled={control.busy} confirmMessage="Salir del chat?" tone="danger" />
          </div>

          <div className="menu-subgrid">
            {recentHistory.map((entry, index) => {
              const historyIndex = -(index + 1)
              return (
                <div className="menu-row" key={`good-${historyIndex}-${entry.role}-${index}`}>
                  <div className="menu-row-main">
                    <strong>{index === 0 ? 'Marcar ultimo como good' : `Marcar ${index + 1}º`}</strong>
                    <span>{compact(entry.content, 74)}</span>
                  </div>
                  <div className="chip-row">
                    <Button
                      label="Good"
                      command={index === 0 ? '/good' : `/good ${historyIndex}`}
                      control={control}
                      disabled={control.busy}
                    />
                  </div>
                </div>
              )
            })}
          </div>

          <div className="menu-list">
            {sessions.map((session) => (
              <div className="menu-row" key={session.sid}>
                <div className="menu-row-main">
                  <strong>{session.sid}</strong>
                  <span>{session.label}</span>
                </div>
                <Button
                  label="Cargar"
                  command={session.command}
                  control={control}
                  disabled={control.busy}
                />
              </div>
            ))}
            {!sessions.length ? <div className="empty-state slim">No hay sesiones guardadas.</div> : null}
          </div>
        </Section>

        <Section
          title="Providers y modelos"
          description="Cambiar provider o modelo con un clic. Cada provider despliega sus modelos."
          meta="switch"
        >
          <div className="chip-row">
            <Button label="/providers" command="/providers" control={control} disabled={control.busy} />
            <Button label="/suggest" command="/suggest" control={control} disabled={control.busy} />
            <Button label="/models" command="/models" control={control} disabled={control.busy} />
          </div>

          <div className="menu-provider-grid">
            {control.providers.map((provider) => (
              <article className={`menu-card provider-card ${provider.active ? 'active' : ''}`} key={provider.name}>
                <div className="menu-row-main provider-head">
                  <div>
                    <strong>{provider.name}</strong>
                    <span>{provider.configured ? 'configurado' : 'sin configurar'} · {(provider.models || []).length} modelos</span>
                  </div>
                  <Button
                    label={provider.active ? 'Activo' : 'Activar'}
                    command={`/switch ${provider.name}`}
                    control={control}
                    disabled={control.busy || provider.active}
                  />
                </div>
                <div className="chip-wrap">
                  {(provider.models || []).map((model) => (
                    <Button
                      key={`${provider.name}-${model}`}
                      label={compact(model, 24)}
                      command={`/switch ${provider.name} ${model}`}
                      control={control}
                      disabled={control.busy}
                      title={`${provider.name}/${model}`}
                    />
                  ))}
                </div>
              </article>
            ))}
            {!control.providers.length ? <div className="empty-state slim">No hay providers cargados.</div> : null}
          </div>

          <div className="menu-note">
            Provider activo: <strong>{control.session?.provider || '-'}</strong> · modelo activo: <strong>{control.session?.model || '-'}</strong>
          </div>
          <div className="chip-wrap">
            {selectedProviderModels.map((model) => (
              <Button
                key={model.id}
                label={compact(model.id, 26)}
                command={`/switch ${control.session?.provider || config.default_provider || ''} ${model.id}`}
                control={control}
                disabled={control.busy || !control.session?.provider}
                title={`${control.session?.provider || ''}/${model.id}`}
              />
            ))}
          </div>
        </Section>

        <Section
          title="Herramientas y automatizacion"
          description="Herramientas, scripts, aprobaciones y ejecucion guiada desde el menu."
          meta="tools"
        >
          <div className="chip-row">
            <Button label="/tools" command="/tools" control={control} disabled={control.busy} />
            <Button label="/tools enable" command="/tools enable" control={control} disabled={control.busy} />
            <Button label="/tools disable" command="/tools disable" control={control} disabled={control.busy} />
            <Button label="/allow" command="/allow" control={control} disabled={control.busy} />
            <Button label="/deny" command="/deny" control={control} disabled={control.busy} />
          </div>

          <div className="chip-row">
            <Button label="/feedback -1" command="/feedback -1" control={control} disabled={control.busy} />
            <Button label="/feedback 0" command="/feedback 0" control={control} disabled={control.busy} />
            <Button label="/feedback 1" command="/feedback 1" control={control} disabled={control.busy} />
            <Button label="/scripts" command="/scripts" control={control} disabled={control.busy} />
          </div>

          <div className="menu-list">
            {tools.map((tool) => (
              <div className="menu-row" key={tool.name}>
                <div className="menu-row-main">
                  <strong>{tool.name}</strong>
                  <span>{tool.description}</span>
                </div>
              </div>
            ))}
            {!tools.length ? <div className="empty-state slim">No hay tools registradas.</div> : null}
          </div>

          <div className="menu-list">
            {scripts.map((battery) => (
              <div className="menu-row" key={battery.id}>
                <div className="menu-row-main">
                  <strong>{battery.id}</strong>
                  <span>{battery.description}</span>
                </div>
                <Button
                  label="Abrir"
                  command={`/scripts ${battery.id}`}
                  control={control}
                  disabled={control.busy}
                />
              </div>
            ))}
            {!scripts.length ? <div className="empty-state slim">No hay baterias registradas.</div> : null}
          </div>

          <div className="menu-list">
            {userPrompts.map((item, index) => {
              const prompt = compact(item.content, 88)
              const commandArg = String(item.content || '').replace(/\s+/g, ' ').trim()
              return (
                <div className="menu-row" key={`prompt-${index}-${prompt}`}>
                  <div className="menu-row-main">
                    <strong>Prompt {index + 1}</strong>
                    <span>{prompt}</span>
                  </div>
                  <div className="chip-row">
                    <Button
                      label="Plan"
                      command={`/plan ${commandArg}`}
                      control={control}
                      disabled={control.busy}
                      title={commandArg}
                    />
                    <Button
                      label="Autopilot"
                      command={`/autopilot ${commandArg}`}
                      control={control}
                      disabled={control.busy}
                      title={commandArg}
                    />
                  </div>
                </div>
              )
            })}
            {!userPrompts.length ? <div className="empty-state slim">No hay prompts recientes para planificar.</div> : null}
          </div>
        </Section>

        <Section
          title="Agentes y memoria"
          description="Activa agentes especializados y opera sobre la memoria persistente."
          meta="agents"
        >
          <div className="chip-row">
            <Button label="/agents" command="/agents" control={control} disabled={control.busy} />
            <Button label="/memory list" command="/memory list" control={control} disabled={control.busy} />
          </div>

          <div className="menu-list">
            {agents.map((agent) => (
              <div className="menu-row" key={agent.name}>
                <div className="menu-row-main">
                  <strong>{agent.name}</strong>
                  <span>{agent.description}</span>
                </div>
                <Button
                  label="Activar"
                  command={`/agent ${agent.name}`}
                  control={control}
                  disabled={control.busy}
                />
              </div>
            ))}
            {!agents.length ? <div className="empty-state slim">No hay agentes disponibles.</div> : null}
          </div>

          <div className="menu-list">
            {memories.map((memory) => (
              <div className="menu-row" key={memory.id}>
                <div className="menu-row-main">
                  <strong>#{memory.id}</strong>
                  <span>{compact(memory.content, 82)}</span>
                </div>
                <div className="chip-row">
                  <Button
                    label="Buscar"
                    command={memory.search_command}
                    control={control}
                    disabled={control.busy}
                    title={memory.content}
                  />
                  <Button
                    label="Añadir"
                    command={memory.add_command}
                    control={control}
                    disabled={control.busy}
                    title={memory.content}
                  />
                  <Button
                    label="Hibrido"
                    command={memory.hybrid_add_command}
                    control={control}
                    disabled={control.busy}
                    title={memory.content}
                  />
                  <Button
                    label="Borrar"
                    command={memory.delete_command}
                    control={control}
                    disabled={control.busy}
                    confirmMessage={`Eliminar recuerdo ${memory.id}?`}
                    tone="danger"
                  />
                </div>
              </div>
            ))}
            {!memories.length ? <div className="empty-state slim">No hay recuerdos recientes.</div> : null}
          </div>
        </Section>

        <Section
          title="Configuracion y credenciales"
          description="Toggles frecuentes y credenciales guardadas en un solo panel."
          meta="config"
        >
          <div className="chip-row">
            <Button label="/config list" command="/config list" control={control} disabled={control.busy} />
            <Button label="/config reset" command="/config reset" control={control} disabled={control.busy} confirmMessage="Restaurar la configuracion por defecto?" tone="danger" />
          </div>

          <div className="menu-toggle-grid">
            <div className="menu-toggle-card">
              <strong>default_provider</strong>
              <span>{config.default_provider || '-'}</span>
              <div className="chip-wrap">
                {control.providers.map((provider) => (
                  <Button
                    key={`dp-${provider.name}`}
                    label={provider.name}
                    command={`/config set default_provider ${provider.name}`}
                    control={control}
                    disabled={control.busy}
                  />
                ))}
              </div>
            </div>

            <div className="menu-toggle-card">
              <strong>default_model</strong>
              <span>{config.default_model || '-'}</span>
              <div className="chip-wrap">
                {selectedProviderModels.map((model) => (
                  <Button
                    key={`dm-${model.id}`}
                    label={compact(model.id, 24)}
                    command={`/config set default_model ${model.id}`}
                    control={control}
                    disabled={control.busy}
                  />
                ))}
              </div>
            </div>

            <div className="menu-toggle-card">
              <strong>model_catalog.mode</strong>
              <span>{config.model_catalog?.mode || '-'}</span>
              <div className="chip-wrap">
                <Button
                  label="all"
                  command="/config set model_catalog.mode all"
                  control={control}
                  disabled={control.busy}
                />
                <Button
                  label="available-only"
                  command="/config set model_catalog.mode available-only"
                  control={control}
                  disabled={control.busy}
                />
              </div>
            </div>

            <div className="menu-toggle-card">
              <strong>Features</strong>
              <span>Streaming, tools y RL learning</span>
              <div className="chip-wrap">
                <Button
                  label={`streaming ${config.features?.streaming ? 'on' : 'off'}`}
                  command={`/config set features.streaming ${!config.features?.streaming}`}
                  control={control}
                  disabled={control.busy}
                />
                <Button
                  label={`tool_calling ${config.features?.tool_calling ? 'on' : 'off'}`}
                  command={`/config set features.tool_calling ${!config.features?.tool_calling}`}
                  control={control}
                  disabled={control.busy}
                />
                <Button
                  label={`auto_allow ${config.features?.auto_allow_tools ? 'on' : 'off'}`}
                  command={`/config set features.auto_allow_tools ${!config.features?.auto_allow_tools}`}
                  control={control}
                  disabled={control.busy}
                />
                <Button
                  label={`rl_learning ${config.features?.rl_learning ? 'on' : 'off'}`}
                  command={`/config set features.rl_learning ${!config.features?.rl_learning}`}
                  control={control}
                  disabled={control.busy}
                />
                <Button
                  label={`prompt_on_start ${config.ui?.prompt_provider_on_start ? 'on' : 'off'}`}
                  command={`/config set ui.prompt_provider_on_start ${!config.ui?.prompt_provider_on_start}`}
                  control={control}
                  disabled={control.busy}
                />
              </div>
            </div>
          </div>

          <form className="credentials-form" onSubmit={saveCredential}>
            <div className="credentials-form-head">
              <div>
                <h4>Credenciales</h4>
                <span>Guardado local y enmascarado en la vista.</span>
              </div>
              <Button label="/credentials list" command="/credentials list" control={control} disabled={control.busy} />
            </div>

            <div className="credentials-grid">
              <label>
                Provider
                <select
                  value={credentialProvider}
                  onChange={(event) => setCredentialProvider(event.target.value)}
                  disabled={control.busy}
                >
                  <option value="">Elegir provider</option>
                  {schemaProviders.map((provider) => (
                    <option key={provider} value={provider}>{provider}</option>
                  ))}
                </select>
              </label>
              <label>
                Key
                <select
                  value={credentialKey}
                  onChange={(event) => setCredentialKey(event.target.value)}
                  disabled={control.busy || !credentialProvider}
                >
                  <option value="">Elegir key</option>
                  {Array.from(new Set([
                    ...Object.keys(credentialsSchema[credentialProvider] || {}),
                    ...Object.keys(credentials[credentialProvider] || {}),
                  ])).map((key) => (
                    <option key={key} value={key}>{key}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="credentials-value">
              Valor
              <input
                value={credentialValue}
                onChange={(event) => setCredentialValue(event.target.value)}
                placeholder="sk-..."
                disabled={control.busy || !credentialProvider || !credentialKey}
              />
            </label>

            <div className="credentials-actions">
              <button type="submit" disabled={control.busy || !canSaveCredential}>
                Guardar credencial
              </button>
            </div>

            <div className="menu-list">
              {Object.entries(credentials).map(([provider, entries]) => (
                <div className="menu-credential-card" key={provider}>
                  <div className="menu-row-main">
                    <strong>{provider}</strong>
                    <span>{Object.keys(entries).length} claves</span>
                  </div>
                  <div className="menu-list compact">
                    {Object.entries(entries).map(([key, masked]) => (
                      <div className="menu-row menu-credential-row" key={`${provider}-${key}`}>
                        <div className="menu-row-main">
                          <strong>{key}</strong>
                          <span>{masked}</span>
                        </div>
                        <Button
                          label="Borrar"
                          command={`/credentials delete ${provider} ${key}`}
                          control={control}
                          disabled={control.busy}
                          confirmMessage={`Eliminar credencial ${provider}/${key}?`}
                          tone="danger"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {!Object.keys(credentials).length ? <div className="empty-state slim">No hay credenciales guardadas.</div> : null}
            </div>
          </form>
        </Section>

        <Section
          title="Sistema"
          description="Acciones globales y estados de control del runtime."
          meta="global"
        >
          <div className="chip-row">
            <Button label="/status" command="/status" control={control} disabled={control.busy} />
            <Button label="/menu" command="/menu" control={control} disabled={control.busy} />
          </div>

          <div className="menu-note">
            Simulacion: <strong>{control.simulation?.mode || 'shadow'}</strong> · RL bridge: <strong>{control.rl?.mode || '-'}</strong> · Catalogo: <strong>{control.catalog?.mode || 'all'}</strong>
          </div>
        </Section>
      </div>
    </section>
  )
}
