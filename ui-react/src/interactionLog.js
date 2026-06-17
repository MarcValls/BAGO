const STORAGE_KEY = 'bago.interaction.log'
const MAX_ENTRIES = 200

function safeClone(value) {
  try {
    return value == null ? null : JSON.parse(JSON.stringify(value))
  } catch {
    return String(value)
  }
}

function readLog() {
  if (typeof window === 'undefined') return []
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export function recordInteraction(event, payload = {}) {
  if (typeof window === 'undefined') return null
  const entry = {
    ts: new Date().toISOString(),
    source: 'ui-react',
    event,
    payload: safeClone(payload),
  }
  const next = [entry, ...readLog()].slice(0, MAX_ENTRIES)
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  } catch {}
  window.__bagoInteractionLog = next
  try {
    window.dispatchEvent(new CustomEvent('bago:interaction', { detail: entry }))
  } catch {}
  return entry
}

export function getInteractionLog() {
  if (typeof window === 'undefined') return []
  return window.__bagoInteractionLog || readLog()
}
