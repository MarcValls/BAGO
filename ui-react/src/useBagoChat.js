import { useCallback, useEffect, useRef, useState } from 'react'
import { chatApi } from './api'
import { recordInteraction } from './interactionLog'

export function useBagoChat() {
  const [mode, setMode] = useState('manager')
  const [session, setSession] = useState(null)
  const [history, setHistory] = useState([])
  const [models, setModels] = useState([])
  const [menu, setMenu] = useState(null)
  const [commandLog, setCommandLog] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const busyRef = useRef(false)

  const pushCommandLog = useCallback((entry) => {
    setCommandLog((current) => [
      {
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        timestamp: new Date().toISOString(),
        ...entry,
      },
      ...current,
    ].slice(0, 8))
  }, [])

  const refresh = useCallback(async () => {
    try {
      const [sessionData, historyData, menuData] = await Promise.all([
        chatApi.getSession(),
        chatApi.getHistory(),
        chatApi.getMenu(),
      ])
      setSession(sessionData)
      setHistory(historyData.messages || [])
      setMenu(menuData)
      if (sessionData?.provider) {
        const modelsData = await chatApi.getModels(sessionData.provider)
        setModels(modelsData.items || [])
      } else {
        setModels([])
      }
      setError('')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(() => {
      if (!busyRef.current) {
        refresh()
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  const submit = useCallback(async (input, channel = mode, managerContext = null) => {
    if (!input.trim()) return
    recordInteraction('submit', {
      channel,
      mode,
      kind: input.trim().startsWith('/') ? 'command' : 'chat',
      input: input.trim(),
      managerContext,
    })
    setBusy(true)
    busyRef.current = true
    try {
      if (input.trim().startsWith('/')) {
        const response = await chatApi.runCommand(input.trim(), channel)
        pushCommandLog({
          kind: 'command',
          channel,
          command: input.trim(),
          response,
        })
      } else {
        await chatApi.sendChat(input.trim(), channel, managerContext)
      }
      await refresh()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [mode, pushCommandLog, refresh])

  const switchProviderModel = useCallback(async (provider, model = '', channel = 'desktop') => {
    if (!provider) return
    recordInteraction('switch-provider-model', {
      channel,
      provider,
      model: model || null,
    })
    setBusy(true)
    busyRef.current = true
    try {
      const response = await chatApi.switchModel(provider, model || null, false, channel)
      pushCommandLog({
        kind: 'switch',
        channel,
        command: `/switch ${provider}${model ? ` ${model}` : ''}`,
        response,
      })
      await refresh()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [pushCommandLog, refresh])

  return {
    mode,
    setMode,
    session,
    history,
    models,
    menu,
    commandLog,
    busy,
    error,
    refresh,
    submit,
    switchProviderModel,
  }
}
