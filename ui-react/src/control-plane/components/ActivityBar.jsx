import { Icon } from './ui'
import { ROOMS, EXTRA_ROOMS } from './constants'

export default function ActivityBar({ activeRoom, navigate, theme, setTheme }) {
  const itemColor = (id) => {
    if (id === 'chat') return EXTRA_ROOMS.chat.color
    if (id === 'jobs') return EXTRA_ROOMS.jobs.color
    const r = ROOMS.find((x) => x.id === id)
    return r?.color || 'var(--cp-text)'
  }

  return (
    <nav className="cp-activity-bar" aria-label="Activity Bar">
      <button
        type="button"
        className={`cp-act-btn ${activeRoom === 'chat' ? 'is-active' : ''}`}
        onClick={() => navigate('chat')}
        title="Chat"
        style={{ color: activeRoom === 'chat' ? EXTRA_ROOMS.chat.color : 'var(--cp-muted)' }}
      >
        <Icon name="chat" size={22} ariaHidden={false} ariaLabel="Chat" />
      </button>
      <div className="cp-act-sep" />
      {ROOMS.map((r) => (
        <button
          key={r.id}
          type="button"
          className={`cp-act-btn ${activeRoom === r.id ? 'is-active' : ''}`}
          onClick={() => navigate(r.id)}
          title={r.label}
          style={{ color: activeRoom === r.id ? r.color : 'var(--cp-muted)' }}
        >
          <Icon name={r.icon} size={22} ariaHidden={false} ariaLabel={r.label} />
        </button>
      ))}
      <button
        type="button"
        className={`cp-act-btn ${activeRoom === 'jobs' ? 'is-active' : ''}`}
        onClick={() => navigate('jobs')}
        title="Jobs"
        style={{ color: activeRoom === 'jobs' ? EXTRA_ROOMS.jobs.color : 'var(--cp-muted)' }}
      >
        <Icon name="bell" size={22} ariaHidden={false} ariaLabel="Jobs" />
      </button>
      <div className="cp-act-spacer" />
      <button
        type="button"
        className="cp-act-btn"
        onClick={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
      >
        {theme === 'dark' ? '☀' : '☾'}
      </button>
    </nav>
  )
}