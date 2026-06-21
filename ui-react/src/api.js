import { recordInteraction } from './interactionLog'

const API_URL = import.meta.env.VITE_BAGO_API_URL
  || (import.meta.env.DEV ? 'http://127.0.0.1:8080' : window.location.origin)
const API_TOKEN = import.meta.env.VITE_BAGO_API_TOKEN || ''

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_TOKEN ? { 'X-Bago-Token': API_TOKEN } : {}),
    ...(options.headers || {}),
  }
  const body = typeof options.body === 'string' ? (() => {
    try { return JSON.parse(options.body) } catch { return options.body }
  })() : options.body || null
  recordInteraction('api-request', {
    path,
    method: options.method || 'GET',
    channel: options.headers?.['X-Bago-Channel'] || options.headers?.['x-bago-channel'] || '',
    body,
  })
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error || data.message || `HTTP ${response.status}`)
  }
  recordInteraction('api-response', {
    path,
    method: options.method || 'GET',
    ok: true,
  })
  return data
}

export const chatApi = {
  getSession: () => request('/session'),
  getHistory: () => request('/history'),
  getMenu: () => request('/menu'),
  getModels: (provider) => request(`/models/${encodeURIComponent(provider)}`),
  getSimulationStatus: () => request('/simulation/status'),
  getSimulationEvents: () => request('/simulation/events'),
  getCatalogStatus: () => request('/catalog/status'),
  getRlStatus: () => request('/rl/status'),
  sendChat: (message, channel, managerContext) => request('/chat', {
    method: 'POST',
    headers: { 'X-Bago-Channel': channel },
    body: JSON.stringify({
      message,
      channel,
      ...(managerContext ? { manager_context: managerContext } : {}),
    }),
  }),
  runCommand: (command, channel) => request('/command', {
    method: 'POST',
    headers: { 'X-Bago-Channel': channel },
    body: JSON.stringify({ command, channel }),
  }),
  switchModel: (provider, model, force = false, channel = 'desktop') => request('/switch', {
    method: 'POST',
    headers: { 'X-Bago-Channel': channel },
    body: JSON.stringify({ provider, model, force, channel }),
  }),
}
