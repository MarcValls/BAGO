import { Component } from 'react'

/**
 * ErrorBoundary — captures render-time exceptions and shows a compact
 * trace instead of a blank black page. Provides a "copy trace" button
 * for quick debugging.
 *
 * Place at the App root, above any component that might throw during render.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    console.error('[BAGO ErrorBoundary]', error, info)
  }

  handleCopyTrace = () => {
    const { error, info } = this.state
    const trace = [
      `BAGO Error Report — ${new Date().toISOString()}`,
      ``,
      `Error: ${error?.name}: ${error?.message}`,
      ``,
      `Stack:`,
      error?.stack || '(no stack)',
      ``,
      `Component Stack:`,
      info?.componentStack || '(no component stack)',
    ].join('\n')

    navigator.clipboard?.writeText(trace).then(
      () => this.setState({ copied: true }),
      () => {},
    )
    setTimeout(() => this.setState({ copied: false }), 2000)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }

    const { error, info, copied } = this.state
    const compactTrace = (error?.stack || '').split('\n').slice(0, 6).join('\n')

    return (
      <div className="error-boundary-fallback">
        <div className="error-boundary-card">
          <div className="error-boundary-icon">⚠</div>
          <h1>BAGO encontró un error de renderizado</h1>
          <p className="error-boundary-message">
            {error?.name}: {error?.message}
          </p>

          {compactTrace && (
            <pre className="error-boundary-trace">{compactTrace}</pre>
          )}

          {info?.componentStack && (
            <details className="error-boundary-details">
              <summary>Component stack</summary>
              <pre>{info.componentStack.trim().slice(0, 800)}</pre>
            </details>
          )}

          <div className="error-boundary-actions">
            <button type="button" onClick={this.handleReload}>
              ↻ Recargar
            </button>
            <button type="button" onClick={this.handleCopyTrace}>
              {copied ? '✓ Copiado' : '⎘ Copiar traza'}
            </button>
          </div>
        </div>
      </div>
    )
  }
}