import { useState } from 'react'

export default function ComposeBar({ onSubmit, busy, placeholder }) {
  const [value, setValue] = useState('')

  function handleSubmit(event) {
    event.preventDefault()
    const next = value.trim()
    if (!next) return
    onSubmit(next)
    setValue('')
  }

  return (
    <form className="compose-bar" onSubmit={handleSubmit}>
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        disabled={busy}
      />
      <button type="submit" disabled={busy}>Enviar</button>
    </form>
  )
}
