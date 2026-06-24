import { useEffect, useState } from 'react'

const DEFAULT_CONFIG = {
  version: '4.8.0',
  brand: { name: 'BAGO', symbol: 'B', tagline: 'Conversación equipada' },
  theme: {
    mode: 'dark',
    bg: '#050813',
    bg2: '#08101f',
    panel: '#0f172a',
    panel2: '#121d32',
    panel3: '#17233d',
    text: '#e8eefb',
    muted: '#91a5c0',
    brand: '#7c8cff',
    brandStrong: '#4658ff',
    cyan: '#22d3ee',
    ok: '#34d399',
    warn: '#fbbf24',
    danger: '#fb7185',
    violet: '#c084fc',
    orange: '#fb923c',
    radius: '20px',
  },
  layout: {
    showKit: true,
    showDock: true,
    showInspector: true,
    showContextPane: true,
    showManagerDrawer: true,
    sidebarCollapsed: false,
    chatFocus: false,
  },
  nav: { chat: true, manager: true, terminal: true },
}

let _cachedConfig = DEFAULT_CONFIG

export function getUiConfig() {
  return _cachedConfig
}

const CONFIG_URL = `${import.meta.env.BASE_URL || '/'}ui_config.json`

export function useUiConfig() {
  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(CONFIG_URL, { cache: 'no-store' })
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) {
          _cachedConfig = { ...DEFAULT_CONFIG, ...data }
          setConfig(_cachedConfig)
          setLoaded(true)
        }
      })
      .catch(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!loaded) return
    const root = document.documentElement
    const t = config.theme
    root.style.setProperty('--bg', t.bg)
    root.style.setProperty('--bg2', t.bg2)
    root.style.setProperty('--panel', t.panel)
    root.style.setProperty('--panel2', t.panel2)
    root.style.setProperty('--panel3', t.panel3)
    root.style.setProperty('--text', t.text)
    root.style.setProperty('--muted', t.muted)
    root.style.setProperty('--brand', t.brand)
    root.style.setProperty('--brand-strong', t.brandStrong)
    root.style.setProperty('--cyan', t.cyan)
    root.style.setProperty('--ok', t.ok)
    root.style.setProperty('--warn', t.warn)
    root.style.setProperty('--danger', t.danger)
    root.style.setProperty('--violet', t.violet)
    root.style.setProperty('--orange', t.orange)
    root.style.setProperty('--radius', t.radius)
    root.setAttribute('data-theme', t.mode)
  }, [config, loaded])

  return { config, loaded }
}

export default useUiConfig