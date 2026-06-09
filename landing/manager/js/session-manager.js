let pmSessions = []
let pmSession = null
let pmChatTabs = []
let pmTabsRestored = false
const PM_CHAT_TABS_KEY = 'bago.manager.chat-tabs.v1'

function pmSessionApi(args) {
  const api = electronApi()
  if (!api || !api.runSessionCommand) throw new Error('SessionManager solo esta disponible en Electron')
  return api.runSessionCommand(args)
}

function pmSessionOption(value, label, selected) {
  return '<option value="' + escapeHtml(value) + '"' + (selected === true || value === selected ? ' selected' : '') + '>' + escapeHtml(label || value) + '</option>'
}

function pmChatTitle(session) {
  if (!session) return 'Chat'
  const provider = session.provider || session.last_provider || 'sin provider'
  const model = session.model || session.last_model || 'sin modelo'
  return provider + ' · ' + model
}

function pmChatSubtitle(session) {
  if (!session) return 'sin provider · sin modelo'
  return session.session_id || session.sid || 'chat'
}

function pmPersistChatTabs() {
  try {
    localStorage.setItem(PM_CHAT_TABS_KEY, JSON.stringify({
      active: pmSession && pmSession.session_id ? pmSession.session_id : '',
      tabs: pmChatTabs.map((item) => item.sid),
    }))
  } catch {}
}

async function pmRestoreChatTabs() {
  if (pmTabsRestored) return
  pmTabsRestored = true
  let stored = null
  try {
    stored = JSON.parse(localStorage.getItem(PM_CHAT_TABS_KEY) || 'null')
  } catch {}
  const tabs = Array.isArray(stored && stored.tabs) ? stored.tabs : []
  const active = String(stored && stored.active || '').trim()
  for (const sid of tabs) {
    if (!sid) continue
    try {
      const result = await pmSessionApi(['status', '--session-id', sid])
      pmSyncChatTab(result.session, false)
    } catch {}
  }
  if (active) {
    const selected = pmChatTabs.find((item) => item.sid === active)
    if (selected) pmSession = selected.session || null
  }
  if (!pmSession && pmChatTabs.length) {
    pmSession = pmChatTabs[0].session || null
  }
  pmPersistChatTabs()
}

function pmSyncChatTab(session, persist = true) {
  if (!session || !session.session_id) return
  const sid = session.session_id
  const existing = pmChatTabs.find((item) => item.sid === sid)
  if (existing) {
    existing.session = session
  } else {
    pmChatTabs.push({ sid, session })
  }
  pmSession = session
  if (persist) pmPersistChatTabs()
}

function pmSelectChatTab(sessionId) {
  const tab = pmChatTabs.find((item) => item.sid === sessionId)
  if (!tab) return
  pmSession = tab.session
  pmPersistChatTabs()
  pmRenderSession()
}

function pmCloseChatTab(sessionId) {
  pmChatTabs = pmChatTabs.filter((item) => item.sid !== sessionId)
  if (pmSession && pmSession.session_id === sessionId) {
    pmSession = pmChatTabs[0]?.session || null
  }
  pmPersistChatTabs()
  pmRenderSession()
}

function pmRenderSessionTabs() {
  const box = document.getElementById('pm-session-tabs')
  if (!box) return
  if (!pmChatTabs.length) {
    box.innerHTML = '<div class="pm-empty">Sin chats abiertos. Usa "Nueva pestaña" para empezar.</div>'
    return
  }
  box.innerHTML = pmChatTabs.map((item) => {
    const session = item.session || {}
    const active = pmSession && pmSession.session_id === item.sid
    return (
      '<button type="button" class="pm-chat-tab ' + (active ? 'active' : '') + '" data-chat-tab="' + escapeHtml(item.sid) + '">' +
        '<div class="pm-chat-tab-copy">' +
          '<strong>' + escapeHtml(pmChatTitle(session)) + '</strong>' +
          '<span>' + escapeHtml(pmChatSubtitle(session)) + '</span>' +
        '</div>' +
        '<span class="pm-chat-tab-close" data-chat-close="' + escapeHtml(item.sid) + '" aria-label="Cerrar chat">×</span>' +
      '</button>'
    )
  }).join('') + '<button type="button" class="pm-chat-tab new" data-chat-new>+ Chat</button>'
}

function pmRenderSessionList() {
  const box = document.getElementById('pm-session-list')
  box.innerHTML = pmSessions.map((item) => (
    '<div class="pm-row ' + (pmSession && pmSession.session_id === item.sid ? 'selected' : '') + '" data-session-id="' + escapeHtml(item.sid) + '">' +
      '<span class="pm-row-icon">S</span>' +
      '<div>' +
        '<h3>' + escapeHtml(item.sid) + '</h3>' +
        '<p>' + escapeHtml((item.provider || item.last_provider || 'sin provider') + ' · ' + (item.model || item.last_model || 'sin modelo')) + '</p>' +
        '<div class="pm-badges">' + pmBadge(item.bago_mode || 'B', 'info') + pmBadge(item.active_agent || 'default') + '</div>' +
      '</div>' +
    '</div>'
  )).join('') || '<div class="pm-empty">Sin sesiones persistidas.</div>'
  box.querySelectorAll('[data-session-id]').forEach((row) => row.addEventListener('click', () => pmOpenChatTab(row.getAttribute('data-session-id'))))
}

function pmRenderSessionChat() {
  const box = document.getElementById('pm-session-chat')
  const prompt = document.getElementById('pm-session-prompt')
  const send = document.getElementById('pm-session-send')
  const orchestrate = document.getElementById('pm-session-orchestrate')
  if (!box) return
  const session = pmSession
  box.innerHTML = session
    ? (session.history || []).map((message) => (
      '<div class="pm-session-message ' + escapeHtml(message.role || '') + '">' +
        '<strong>' + escapeHtml(message.role || 'message') + '</strong>' +
        escapeHtml(message.content || '') +
      '</div>'
    )).join('') || '<div class="pm-empty">Sin historial.</div>'
    : '<div class="pm-empty">Sin chat abierto. Crea una pestaña para empezar.</div>'
  if (prompt) prompt.disabled = !session
  if (send) send.disabled = !session
  if (orchestrate) orchestrate.disabled = !session
}

function pmRenderSession() {
  if (!pmSession && pmChatTabs.length) pmSession = pmChatTabs[0].session || null
  pmRenderSessionList()
  pmRenderSessionTabs()
  pmRenderSessionChat()
  const session = pmSession
  document.getElementById('pm-session-active').textContent = session ? session.session_id + ' · ' + session.provider + ' / ' + session.model : 'Selecciona o crea una sesión'
  const providers = session && Array.isArray(session.providers) ? session.providers : []
  document.getElementById('pm-session-provider').innerHTML = providers.map((item) => pmSessionOption(item.name, item.name + (item.configured ? ' · listo' : ' · no configurado'), session && session.provider)).join('')
  const current = providers.find((item) => session && item.name === session.provider)
  const models = current && current.models && current.models.length ? current.models : [session && session.model || '']
  document.getElementById('pm-session-model').innerHTML = models.filter(Boolean).map((model) => pmSessionOption(model, model, session && session.model)).join('')
  document.getElementById('pm-session-mode').value = session && session.bago_mode || 'B'
  document.getElementById('pm-session-agent').innerHTML = (session && session.agents || ['default']).map((agent) => pmSessionOption(agent, agent, session && session.active_agent)).join('')
  document.getElementById('pm-session-bridges').innerHTML = providers.map((item) => pmSessionOption(item.name, item.name, session && (session.active_bridges || []).includes(item.name))).join('')
  document.getElementById('pm-session-status').innerHTML = session ? [
    pmBadge(session.health && session.health.ok ? 'provider listo' : 'provider con fallo', session.health && session.health.ok ? 'ok' : 'bad'),
    pmBadge(String(session.messages || 0) + ' mensajes'),
    pmBadge(String(session.total_calls || 0) + ' llamadas'),
    pmBadge(String(session.total_tokens || 0) + ' tokens')
  ].join('') : ''
}

async function pmLoadSessions() {
  try {
    const result = await pmSessionApi(['list'])
    pmSessions = result.sessions || []
    document.getElementById('pm-session-caption').textContent = pmSessions.length + ' sesiones · ' + (result.base_path || 'runtime activo')
    if (!pmTabsRestored) await pmRestoreChatTabs()
    pmRenderSessionList()
    pmRenderSessionTabs()
  } catch (error) {
    showToast(error.message, false)
  }
}

async function pmOpenChatTab(id) {
  const sessionId = String(id || '').trim()
  if (!sessionId) return pmCreateSession()
  const existing = pmChatTabs.find((item) => item.sid === sessionId)
  if (existing) {
    pmSession = existing.session || null
    pmPersistChatTabs()
    pmRenderSession()
    return pmSession
  }
  try {
    const result = await pmSessionApi(['status', '--session-id', sessionId])
    pmSyncChatTab(result.session)
    await pmLoadSessions()
    pmRenderSession()
    return result.session
  } catch (error) {
    showToast(error.message, false)
    return null
  }
}

async function pmLoadSession(id) {
  return pmOpenChatTab(id)
}

async function pmCreateSession() {
  try {
    const result = await pmSessionApi(['create'])
    pmSyncChatTab(result.session)
    await pmLoadSessions()
    pmRenderSession()
    showToast('Pestaña creada', true)
    return result.session
  } catch (error) {
    showToast(error.message, false)
    return null
  }
}

async function pmApplySession() {
  if (!pmSession) return
  const bridges = [...document.getElementById('pm-session-bridges').selectedOptions].map((option) => option.value).join(',')
  const args = ['apply', '--session-id', pmSession.session_id, '--provider', document.getElementById('pm-session-provider').value, '--model', document.getElementById('pm-session-model').value, '--mode', document.getElementById('pm-session-mode').value, '--agent', document.getElementById('pm-session-agent').value, '--bridges', bridges, '--force']
  try {
    const result = await pmSessionApi(args)
    pmSyncChatTab(result.session)
    await pmLoadSessions()
    pmRenderSession()
    showToast('Sesion actualizada', true)
  } catch (error) {
    showToast(error.message, false)
  }
}

async function pmSendSession(orchestrate = false) {
  if (!pmSession) return
  const input = document.getElementById('pm-session-prompt')
  const prompt = input.value.trim()
  if (!prompt) return
  input.disabled = true
  const args = ['send', '--session-id', pmSession.session_id, '--prompt', prompt]
  if (orchestrate) args.push('--orchestrate')
  try {
    const result = await pmSessionApi(args)
    pmSyncChatTab(result.session)
    input.value = ''
    pmRenderSession()
    if (orchestrate && Object.values(result.response || {}).some((item) => !item.ok)) showToast('Orquestacion parcial: revisa respuestas', false)
  } catch (error) {
    showToast(error.message, false)
  } finally {
    input.disabled = false
  }
}

function pmInitSessions() {
  document.getElementById('pm-session-refresh').addEventListener('click', pmLoadSessions)
  document.getElementById('pm-session-create').addEventListener('click', pmCreateSession)
  document.getElementById('pm-session-apply').addEventListener('click', pmApplySession)
  document.getElementById('pm-session-send').addEventListener('click', () => pmSendSession(false))
  document.getElementById('pm-session-orchestrate').addEventListener('click', () => pmSendSession(true))
  const tabsBox = document.getElementById('pm-session-tabs')
  if (tabsBox) {
    tabsBox.addEventListener('click', async (event) => {
      const close = event.target.closest('[data-chat-close]')
      if (close) {
        pmCloseChatTab(close.getAttribute('data-chat-close'))
        return
      }
      if (event.target.closest('[data-chat-new]')) {
        await pmCreateSession()
        return
      }
      const tab = event.target.closest('[data-chat-tab]')
      if (tab) {
        pmSelectChatTab(tab.getAttribute('data-chat-tab'))
      }
    })
  }
  document.getElementById('pm-session-provider').addEventListener('change', (event) => {
    if (!pmSession) return
    const provider = (pmSession.providers || []).find((item) => item.name === event.target.value)
    document.getElementById('pm-session-model').innerHTML = ((provider && provider.models) || []).map((model) => pmSessionOption(model, model, '')).join('')
  })
  window.pmOpenChatTab = pmOpenChatTab
  window.pmSelectChatTab = pmSelectChatTab
  window.pmCreateChatTab = pmCreateSession
  window.pmPersistChatTabs = pmPersistChatTabs
  pmLoadSessions()
}

pmInitSessions()
