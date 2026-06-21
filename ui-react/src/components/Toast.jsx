import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const ToastContext = createContext({ push: () => {} })

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)

  const push = useCallback((message, kind = 'info', ttl = 2200) => {
    setToast({ id: Date.now() + Math.random().toString(16).slice(2, 6), message, kind })
  }, [])

  useEffect(() => {
    if (!toast) return undefined
    const timer = setTimeout(() => setToast(null), toast.ttl || 2200)
    return () => clearTimeout(timer)
  }, [toast])

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      {toast ? (
        <div className={`toast toast-${toast.kind}`} role="status" aria-live="polite">
          {toast.message}
        </div>
      ) : null}
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
