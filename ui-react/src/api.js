const API_URL = import.meta.env.VITE_BAGO_API_URL
  || (import.meta.env.DEV ? 'http://127.0.0.1:8080' : window.location.origin)
const API_TOKEN = import.meta.env.VITE_BAGO_API_TOKEN || ''

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(API_TOKEN ? { 'X-Bago-Token': API_TOKEN } : {}),
    ...(options.headers || {}),
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error || data.message || `HTTP ${response.status}`)
  }
  return data
}

export const bagoApi = {
  getSession: () => request('/session'),
  getStatus: () => request('/status'),
  getHistory: () => request('/history'),
  getProviders: () => request('/providers'),
  getMenu: () => request('/menu'),
  getModels: (provider) => request(`/models/${encodeURIComponent(provider)}`),
  getCatalogStatus: () => request('/catalog/status'),
  setCatalogMode: (mode) => request('/catalog/config', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  }),
  getSimulationStatus: () => request('/simulation/status'),
  getSimulationEvents: () => request('/simulation/events'),
  getRlStatus: () => request('/rl/status'),
  setRlShadow: (enabled = true) => request('/rl/shadow', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  }),
  setSimulationMode: (mode, enabled = true) => request('/simulation/config', {
    method: 'POST',
    body: JSON.stringify({ mode, enabled }),
  }),
  sendChat: (message, channel) => request('/chat', {
    method: 'POST',
    headers: { 'X-Bago-Channel': channel },
    body: JSON.stringify({ message, channel }),
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
