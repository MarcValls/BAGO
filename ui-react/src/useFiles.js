import { useCallback, useState } from 'react'
import { chatApi } from './api'

export function useFiles() {
  const [files, setFiles] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await chatApi.getFilesList()
      setFiles(data)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  return { files, loading, error, refresh }
}