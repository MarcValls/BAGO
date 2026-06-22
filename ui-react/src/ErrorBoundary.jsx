import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, stack: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error: error?.message || String(error), stack: error?.stack || '' }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, fontFamily: 'monospace', color: '#ff6b6b', background: '#1a1a2e', minHeight: '100vh' }}>
          <h2>React crash — ErrorBoundary</h2>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{this.state.error}</pre>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, color: '#888', marginTop: 16 }}>{this.state.stack}</pre>
          <button
            onClick={() => this.setState({ hasError: false, error: null, stack: null })}
            style={{ marginTop: 16, padding: '8px 16px', background: '#4a4a6a', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
          >
            Reintentar
          </button>
        </div>
      )
    }
    return this.props.children
  }
}