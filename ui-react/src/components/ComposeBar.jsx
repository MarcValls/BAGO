import { useState } from 'react'

export default function ComposeBar({ onSubmit, busy, placeholder, accessory }) {
  const [value, setValue] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const next = value.trim()
    if (!next) return
    onSubmit(next)
    setValue('')
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit(event)
    }
  }

  return (
    <form className="compose-bar" onSubmit={handleSubmit}>
      <textarea
        rows={1}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={busy}
        aria-label="Mensaje"
      />
      <div className="compose-actions">
        <div className="compose-accessory">{accessory}</div>
        <button className="send-button" type="submit" disabled={busy || !value.trim()} aria-label="Enviar">
          <svg aria-hidden="true" viewBox="0 0 24 24">
            <path d="M12 19V5M6.5 10.5 12 5l5.5 5.5" />
          </svg>
        </button>
      </div>
    </form>
  )
}
