import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { bagoApi } from './api'
import { recordInteraction } from './interactionLog'

export function useBagoControl() {
  const [mode, setMode] = useState('terminal')
  const [session, setSession] = useState(null)
  const [history, setHistory] = useState([])
  const [providers, setProviders] = useState([])
  const [models, setModels] = useState([])
  const [simulation, setSimulation] = useState(null)
  const [rl, setRl] = useState(null)
  const [events, setEvents] = useState([])
  const [catalog, setCatalog] = useState(null)
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
      const [sessionData, historyData, providersData, simulationData, simulationEventsData, catalogData, menuData, rlData] = await Promise.all([
        bagoApi.getSession(),
        bagoApi.getHistory(),
        bagoApi.getProviders(),
        bagoApi.getSimulationStatus(),
        bagoApi.getSimulationEvents(),
        bagoApi.getCatalogStatus(),
        bagoApi.getMenu(),
        bagoApi.getRlStatus(),
      ])
      setSession(sessionData)
      setHistory(historyData.messages || [])
      setProviders(providersData.providers || [])
      setSimulation(simulationData)
      setRl(rlData)
      setEvents(simulationEventsData.events || [])
      setCatalog(catalogData)
      setMenu(menuData)
      if (sessionData?.provider) {
        const modelsData = await bagoApi.getModels(sessionData.provider)
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
    }, 3000)
    return () => clearInterval(timer)
  }, [refresh])

  const submit = useCallback(async (input, channel = mode) => {
    if (!input.trim()) return
    recordInteraction('submit', {
      channel,
      mode,
      kind: input.trim().startsWith('/') ? 'command' : 'chat',
      input: input.trim(),
    })
    setBusy(true)
    busyRef.current = true
    try {
      if (input.trim().startsWith('/')) {
        const response = await bagoApi.runCommand(input.trim(), channel)
        pushCommandLog({
          kind: 'command',
          channel,
          command: input.trim(),
          response,
        })
      } else {
        await bagoApi.sendChat(input.trim(), channel)
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

  const setSimulationMode = useCallback(async (nextMode) => {
    recordInteraction('simulation-mode', { mode: nextMode })
    setBusy(true)
    busyRef.current = true
    try {
      const next = await bagoApi.setSimulationMode(nextMode, nextMode !== 'off')
      setSimulation(next)
      await refresh()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [refresh])

  const setRlShadow = useCallback(async (enabled) => {
    recordInteraction('rl-shadow', { enabled: !!enabled })
    setBusy(true)
    busyRef.current = true
    try {
      const next = await bagoApi.setRlShadow(enabled)
      setRl(next)
      await refresh()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [refresh])

  const setCatalogMode = useCallback(async (nextMode) => {
    recordInteraction('catalog-mode', { mode: nextMode })
    setBusy(true)
    busyRef.current = true
    try {
      const next = await bagoApi.setCatalogMode(nextMode)
      setCatalog(next)
      await refresh()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [refresh])

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
      const response = await bagoApi.switchModel(provider, model || null, false, channel)
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

  const providerSummary = useMemo(() => {
    return providers.map((provider) => ({
      ...provider,
      active: session?.provider === provider.name,
    }))
  }, [providers, session])

  return {
    mode,
    setMode,
    session,
    history,
    providers: providerSummary,
    models,
    simulation,
    rl,
    events,
    catalog,
    menu,
    commandLog,
    busy,
    error,
    refresh,
    submit,
    setSimulationMode,
    setRlShadow,
    setCatalogMode,
    switchProviderModel,
  }
}
