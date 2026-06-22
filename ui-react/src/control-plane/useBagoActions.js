import { useCallback, useMemo, useState } from 'react'

function getElectron() {
  return typeof window !== 'undefined' ? window.bagoElectron || null : null
}

function unwrap(result) {
  if (result && result.ok === false) {
    throw new Error(result.error || result.message || 'La operación BAGO falló')
  }
  if (result && Object.prototype.hasOwnProperty.call(result, 'data')) return result.data
  return result
}

function cleanTag(value) {
  return String(value || '').trim().replace(/^v/i, '')
}

function safeSuffix(value) {
  return cleanTag(value).replace(/[^A-Za-z0-9._-]/g, '_') || 'release'
}

function preflightIssues(preflight) {
  return [
    ...(Array.isArray(preflight?.prepare_blockers) ? preflight.prepare_blockers : []),
    ...(Array.isArray(preflight?.blockers) ? preflight.blockers : []),
  ].filter(Boolean)
}

function preflightSummary(preflight) {
  const warnings = Array.isArray(preflight?.warnings) ? preflight.warnings : []
  const target = preflight?.target?.path || preflight?.target || 'destino sin resolver'
  const bundle = preflight?.contract?.bundle?.name || 'bundle sin nombre'
  const permission = preflight?.target?.writable
    ? 'escritura disponible'
    : preflight?.target?.requires_elevation
      ? 'requiere elevación'
      : 'escritura no confirmada'
  return [
    `Destino: ${target}`,
    `Bundle: ${bundle}`,
    `Permisos: ${permission}`,
    warnings.length ? `Avisos:\n- ${warnings.join('\n- ')}` : 'Avisos: ninguno',
    '',
    '¿Crear el trabajo verificado?',
  ].join('\n')
}

export function useBagoActions({ context, setContext, navigate, onOpenTerminal, push }) {
  const [busyAction, setBusyAction] = useState('')
  const [lastResult, setLastResult] = useState(null)
  const [error, setError] = useState('')

  const bridge = getElectron()
  const capabilities = useMemo(() => ({
    electron: !!bridge,
    roles: !!bridge?.writeInstallSelection,
    install: !!bridge?.installAction,
    preflight: !!bridge?.runInstallPreflight,
    releases: !!bridge?.preflightRelease && !!bridge?.startReleaseJob,
    jobs: !!bridge?.listReleaseJobs,
    nodes: !!bridge?.runNodeCommand,
    supervisor: !!bridge?.runSupervisorCommand,
    cleanup: !!bridge?.cleanupZombies,
  }), [bridge])

  const notify = useCallback((message) => {
    if (typeof push === 'function' && message) push(String(message))
  }, [push])

  const execute = useCallback(async (label, task, successMessage = '') => {
    if (busyAction) throw new Error(`Ya hay una operación activa: ${busyAction}`)
    setBusyAction(label)
    setError('')
    try {
      const result = await task()
      setLastResult(result ?? null)
      if (successMessage) notify(successMessage)
      return result
    } catch (cause) {
      const message = cause?.message || String(cause)
      setError(message)
      notify(`Error: ${message}`)
      throw cause
    } finally {
      setBusyAction('')
    }
  }, [busyAction, notify])

  const requireBridge = useCallback((method) => {
    const api = getElectron()
    if (!api) throw new Error('El bridge de Electron no está disponible. Abre la Control Plane desde BAGO Manager.')
    if (method && typeof api[method] !== 'function') throw new Error(`El backend no expone ${method}`)
    return api
  }, [])

  const resolveTarget = useCallback((label = 'Ruta de instalación de destino') => {
    const selected = String(context?.install || '').trim()
    if (selected && selected !== 'inst-A') return selected
    if (typeof window === 'undefined') return ''
    return String(window.prompt(label, 'C:\\Program Files\\BAGO') || '').trim()
  }, [context?.install])

  const setRole = useCallback((role, installPath) => execute(
    `role:${role}`,
    async () => {
      const api = requireBridge('writeInstallSelection')
      const path = String(installPath || resolveTarget('Ruta existente para el rol')).trim()
      if (!path) throw new Error('No se indicó una instalación')
      const result = await api.writeInstallSelection(role, path)
      setContext?.((current) => ({ ...current, install: path }))
      return result
    },
    `Rol ${role} actualizado`,
  ), [execute, requireBridge, resolveTarget, setContext])

  const registerInstallation = useCallback(() => execute(
    'register-installation',
    async () => {
      const api = requireBridge('writeInstallSelection')
      const path = String(window.prompt('Ruta existente de la instalación BAGO', '') || '').trim()
      if (!path) throw new Error('Registro cancelado: no se indicó una ruta')
      const roleInput = String(window.prompt('Rol: active, dev o launch', 'dev') || 'dev').trim().toLowerCase()
      if (!['active', 'dev', 'launch'].includes(roleInput)) throw new Error(`Rol no válido: ${roleInput}`)
      const result = await api.writeInstallSelection(roleInput, path)
      setContext?.((current) => ({ ...current, install: path }))
      return result
    },
    'Instalación registrada mediante su rol',
  ), [execute, requireBridge, setContext])

  const runSupervisor = useCallback((command) => execute(
    `supervisor:${command}`,
    async () => {
      const api = requireBridge('runSupervisorCommand')
      return unwrap(await api.runSupervisorCommand([String(command), '--json']))
    },
    `Supervisor: ${command}`,
  ), [execute, requireBridge])

  const cleanupZombies = useCallback(() => execute(
    'cleanup-zombies',
    async () => {
      const api = requireBridge('cleanupZombies')
      return unwrap(await api.cleanupZombies())
    },
    'Limpieza de procesos BAGO completada',
  ), [execute, requireBridge])

  const validateNodes = useCallback(() => execute(
    'node-validate',
    async () => {
      const api = requireBridge('runNodeValidate')
      return unwrap(await api.runNodeValidate())
    },
    'Validación nodular completada',
  ), [execute, requireBridge])

  const prepareRelease = useCallback((release, action = 'install') => execute(
    `release:${action}`,
    async () => {
      const api = requireBridge('preflightRelease')
      if (typeof api.startReleaseJob !== 'function') throw new Error('El backend no permite crear jobs de release')
      if (!release || !release.tag_name) throw new Error('Release no válida')
      const baseTarget = resolveTarget()
      if (!baseTarget) throw new Error('No se indicó el destino')
      const target = action === 'separate' ? `${baseTarget}-${safeSuffix(release.tag_name)}` : baseTarget
      const payload = {
        release,
        target,
        action,
        mode: 'Express',
        require_signature: false,
      }
      const preflight = await api.preflightRelease(payload)
      const blockers = preflightIssues(preflight)
      if (blockers.length) throw new Error(blockers.join(' · '))
      if (typeof window !== 'undefined' && !window.confirm(preflightSummary(preflight))) return null
      const job = await api.startReleaseJob(payload)
      navigate?.('jobs')
      return job
    },
    action === 'separate' ? 'Trabajo Shadow creado' : 'Trabajo de release creado',
  ), [execute, navigate, requireBridge, resolveTarget])

  const runJobAction = useCallback((action, id) => execute(
    `job:${action}`,
    async () => {
      const api = requireBridge()
      const jobId = String(id || '').trim()
      if (!jobId) throw new Error('Job no seleccionado')
      const methods = {
        cancel: 'cancelReleaseJob',
        resume: 'resumeReleaseJob',
        install: 'installReleaseJob',
        rollback: 'rollbackReleaseJob',
        delete: 'deleteReleaseJob',
      }
      const method = methods[action]
      if (!method || typeof api[method] !== 'function') throw new Error(`Acción de job no disponible: ${action}`)
      if (['install', 'rollback', 'delete'].includes(action)) {
        const labels = {
          install: '¿Instalar el bundle verificado? Se creará un backup antes de modificar el destino.',
          rollback: '¿Restaurar el runtime anterior mediante rollback?',
          delete: '¿Archivar este trabajo persistido?',
        }
        if (typeof window !== 'undefined' && !window.confirm(labels[action])) return null
      }
      return unwrap(await api[method](jobId))
    },
    `Job ${action} completado`,
  ), [execute, requireBridge])

  const readJobLogs = useCallback(async (id, limit = 300) => {
    const api = requireBridge('releaseJobLogs')
    return unwrap(await api.releaseJobLogs(String(id || ''), Number(limit || 300))) || []
  }, [requireBridge])

  const mutateNode = useCallback((payload) => execute(
    'node-mutation',
    async () => {
      const api = requireBridge('runNodePreview')
      if (typeof api.runNodeCommand !== 'function') throw new Error('Mutación nodular no disponible')
      const installation = String(payload?.installation || context?.install || '').trim()
      const piece = String(payload?.piece || '').trim()
      const mode = String(payload?.mode || '').trim()
      if (!installation || !piece || !mode) throw new Error('Instalación, pieza y modo son obligatorios')
      const preview = unwrap(await api.runNodePreview(installation, piece, mode))
      const previewText = typeof preview === 'string' ? preview : JSON.stringify(preview, null, 2)
      if (typeof window !== 'undefined' && !window.confirm(`Previsualización nodular:\n\n${previewText.slice(0, 1800)}\n\n¿Aplicar?`)) return null
      const command = mode === 'detached'
        ? ['node', 'disconnect', '--installation', installation, '--piece', piece, '--json']
        : ['node', 'set-mode', '--installation', installation, '--piece', piece, '--mode', mode, '--json']
      return unwrap(await api.runNodeCommand(command))
    },
    'Mutación nodular aplicada',
  ), [context?.install, execute, requireBridge])

  const uninstallInstallation = useCallback((installPath) => execute(
    'uninstall',
    async () => {
      const api = requireBridge('installAction')
      const targetDir = String(installPath || context?.install || '').trim()
      if (!targetDir) throw new Error('Instalación no seleccionada')
      if (typeof api.preflightRelease === 'function') {
        const preflight = await api.preflightRelease({ release: {}, target: targetDir, action: 'uninstall' })
        const blockers = preflightIssues(preflight)
        if (blockers.length) throw new Error(blockers.join(' · '))
      }
      if (typeof window !== 'undefined' && !window.confirm(`¿Archivar esta instalación?\n\n${targetDir}`)) return null
      return unwrap(await api.installAction({ action: 'uninstall', targetDir, purgeState: false }))
    },
    'Instalación archivada',
  ), [context?.install, execute, requireBridge])

  const runAction = useCallback(async (type, payload) => {
    switch (type) {
      case 'open-install':
        setContext?.((current) => ({ ...current, install: payload }))
        navigate?.('installations')
        return payload
      case 'open-node':
        setContext?.((current) => ({ ...current, node: payload }))
        navigate?.('nodes')
        return payload
      case 'open-terminal':
        onOpenTerminal?.(payload)
        return payload
      case 'open-jobs':
        navigate?.('jobs')
        return true
      case 'register':
        return registerInstallation()
      case 'set-role':
        return setRole(payload?.role, payload?.path)
      case 'supervisor-start':
        return runSupervisor('start')
      case 'supervisor-stop':
        return runSupervisor('stop')
      case 'supervisor-status':
      case 'reload':
        return runSupervisor('status')
      case 'cleanup-zombies':
        return cleanupZombies()
      case 'validate-nodes':
        return validateNodes()
      case 'install-release':
        return prepareRelease(payload, 'install')
      case 'shadow-release':
        return prepareRelease(payload, 'separate')
      case 'job-action':
        return runJobAction(payload?.action, payload?.id)
      case 'job-logs':
        return readJobLogs(payload?.id, payload?.limit)
      case 'node-mode':
        return mutateNode(payload)
      case 'uninstall':
        return uninstallInstallation(payload?.path || payload)
      default:
        throw new Error(`La acción ${type} todavía no tiene un contrato backend seguro`)
    }
  }, [cleanupZombies, mutateNode, navigate, onOpenTerminal, prepareRelease, readJobLogs, registerInstallation, runJobAction, runSupervisor, setContext, setRole, uninstallInstallation, validateNodes])

  return {
    capabilities,
    busyAction,
    lastResult,
    error,
    runAction,
    setRole,
    runSupervisor,
    cleanupZombies,
    validateNodes,
    prepareRelease,
    runJobAction,
    readJobLogs,
    mutateNode,
  }
}
