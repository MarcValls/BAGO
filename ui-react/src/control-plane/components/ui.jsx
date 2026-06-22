// Componentes UI compartidos del Control Plane.
// Centraliza Icon, Badge y los wrappers de estado (loading/error/vacio)
// que antes estaban duplicados en cada vista.

import { CPIcons } from '../icons'

// Icon — wrapper accesible del set SVG de control-plane/icons.jsx.
// `ariaHidden` por defecto true (decorativo); pasar false + aria-label si semantico.
export function Icon({ name, size = 18, ariaHidden = true, ariaLabel = '' }) {
  const svg = CPIcons[name]
  if (!svg) return null
  const a11y = ariaHidden
    ? { 'aria-hidden': 'true' }
    : { role: 'img', 'aria-label': ariaLabel || name }
  return (
    <span className="cp-icon" style={{ width: size, height: size }} {...a11y}>
      {svg}
    </span>
  )
}

// Badge — etiqueta de estado con variantes de color.
export function Badge({ children, variant = 'neutral' }) {
  return <span className={`cp-badge cp-badge-${variant}`}>{children}</span>
}

// ViewState — renderiza loading / error / vacio segun el estado de los datos.
// Uso:
//   <ViewState loading={loading} error={error} empty={!data?.length}
//     emptyLabel="Sin instalaciones" />
//   ...contenido...
// Si loading/error/empty son falsy, renderiza children.
export function ViewState({ loading, error, empty, emptyLabel = 'Sin datos', children }) {
  if (loading) {
    return (
      <div className="cp-state cp-state-loading" role="status" aria-live="polite">
        <span className="cp-state-spinner" aria-hidden="true" />
        <span>Cargando…</span>
      </div>
    )
  }
  if (error) {
    return (
      <div className="cp-state cp-state-error" role="alert">
        <strong>Error</strong>
        <span>{error}</span>
      </div>
    )
  }
  if (empty) {
    return (
      <div className="cp-state cp-state-empty" role="status">
        <span>{emptyLabel}</span>
      </div>
    )
  }
  return children ?? null
}