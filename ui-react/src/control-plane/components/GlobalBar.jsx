import { useMemo } from 'react'
import { Icon } from './ui'
import { MENUS } from './constants'

export default function GlobalBar({
  sidebarOpen, setSidebarOpen,
  inspectorOpen, setInspectorOpen,
  theme, setTheme,
  openMenu, setOpenMenu,
  onMenuAction,
  contextInstall,
}) {
  const renderMenuItems = (items, color) => {
    const groups = []
    let current = []
    let currentSection = items[0]?.section || ''
    for (const item of items) {
      if (item.action === 'separator') {
        if (current.length) groups.push({ section: currentSection, items: current })
        current = []
        currentSection = ''
        continue
      }
      if (currentSection && item.section !== currentSection && current.length) {
        groups.push({ section: currentSection, items: current })
        current = []
      }
      currentSection = item.section || ''
      current.push(item)
    }
    if (current.length) groups.push({ section: currentSection, items: current })

    return groups.map((group, gi) => (
      <div key={gi} className="cp-menu-group">
        {group.section ? (
          <div className="cp-menu-section" style={{ color }}>{group.section}</div>
        ) : null}
        {group.items.map((item) => (
          <button
            key={item.id}
            type="button"
            className="cp-menu-item"
            onClick={() => onMenuAction(item.action)}
          >
            <span className="cp-menu-label">
              {item.status ? (
                <span className={`cp-status-dot cp-status-dot-${item.status}`} />
              ) : null}
              {item.label}
            </span>
            {item.shortcut ? <kbd className="cp-menu-kbd">{item.shortcut}</kbd> : null}
          </button>
        ))}
      </div>
    ))
  }

  return (
    <header className="cp-globalbar">
      <div className="cp-global-group cp-global-left">
        <div className="cp-brand" title="BAGO Control Plane">
          <span className="cp-brand-mark">B</span>
          <span className="cp-brand-text">BAGO</span>
        </div>
        <button
          type="button"
          className="cp-toggle"
          onClick={() => setSidebarOpen((v) => !v)}
          aria-label={sidebarOpen ? 'Ocultar sidebar' : 'Mostrar sidebar'}
          title="Sidebar"
        >
          <Icon name={sidebarOpen ? 'arrowLeft' : 'arrowRight'} size={14} />
        </button>
        <button
          type="button"
          className="cp-toggle"
          onClick={() => setInspectorOpen((v) => !v)}
          aria-label={inspectorOpen ? 'Ocultar inspector' : 'Mostrar inspector'}
          title="Inspector"
        >
          <Icon name={inspectorOpen ? 'arrowRight' : 'arrowLeft'} size={14} />
        </button>
        <button
          type="button"
          className="cp-theme-toggle"
          onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
          aria-label={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
          title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
        >
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>

      <nav className="cp-menubar" aria-label="Menú principal">
        {MENUS.map((menu) => {
          const isOpen = openMenu === menu.id
          return (
            <div
              key={menu.id}
              className={`cp-menu cp-menu--${menu.id} ${isOpen ? 'is-open' : ''}`}
              onMouseEnter={() => setOpenMenu(menu.id)}
              onMouseLeave={() => setOpenMenu(null)}
            >
              <button
                type="button"
                className="cp-menu-trigger"
                onClick={() => setOpenMenu(isOpen ? null : menu.id)}
                aria-expanded={isOpen}
                style={{
                  '--menu-color': menu.color,
                }}
              >
                <span className="cp-menu-trigger-icon" style={{ color: menu.color }}>
                  <Icon name={menu.icon} size={14} />
                </span>
                {menu.label}
              </button>
              {isOpen ? (
                <div className="cp-menu-dropdown" style={{ borderTopColor: menu.color }}>
                  <div className="cp-menu-header" style={{ background: menu.color }}>
                    <Icon name={menu.icon} size={14} />
                    <span>{menu.label}</span>
                  </div>
                  {renderMenuItems(menu.items, menu.color)}
                </div>
              ) : null}
            </div>
          )
        })}
      </nav>

      <div className="cp-global-group cp-global-right">
        <div className="cp-sync-pill">
          <span className="cp-status-dot cp-status-dot-ok" />
          Sync
        </div>
        <div className="cp-user-pill">
          <Icon name="user" size={12} />
          {contextInstall || 'inst-A'}
        </div>
      </div>
    </header>
  )
}