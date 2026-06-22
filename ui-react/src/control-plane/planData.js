export const PLANS = [
  {
    id: 'deploy-release',
    label: 'Desplegar release 4.6.1',
    description: 'Build, verificar, parchear e indexar conocimiento.',
    steps: [
      { id: 's1', label: 'Build release', command: 'bago build --release 4.6.1', kind: 'command' },
      { id: 's2', label: 'Run tests', command: 'bago test --suite integration', kind: 'command' },
      { id: 's3', label: 'Health check', command: 'bago health --full', kind: 'command' },
      { id: 's4', label: 'Patch staging', command: 'bago patch --env staging --release 4.6.1', kind: 'command', dependsOn: ['s1', 's2'] },
      { id: 's5', label: 'Index knowledge', command: 'bago knowledge index', kind: 'command', dependsOn: ['s3'] },
      { id: 's6', label: 'Notify chat', command: 'bago notify "Release 4.6.1 listo"', kind: 'command', dependsOn: ['s4', 's5'] },
    ],
  },
  {
    id: 'sync-agents',
    label: 'Sincronizar agentes',
    description: 'Indexar, reconciliar claims y verificar supervisor/runtime.',
    steps: [
      { id: 'a1', label: 'Index knowledge', command: 'bago knowledge index', kind: 'command' },
      { id: 'a2', label: 'Reconcile claims', command: 'bago claims reconcile', kind: 'command' },
      { id: 'a3', label: 'Verify supervisor', command: 'bago agent check supervisor', kind: 'command' },
      { id: 'a4', label: 'Verify runtime', command: 'bago agent check runtime', kind: 'command' },
      { id: 'a5', label: 'Compact log', command: 'bago log compact', kind: 'command', dependsOn: ['a1'] },
    ],
  },
  {
    id: 'audit-cycle',
    label: 'Ciclo de auditoría',
    description: 'Recopilar evidencia, escanear nodos y generar reporte.',
    steps: [
      { id: 'e1', label: 'Collect evidence', command: 'bago audit collect', kind: 'command' },
      { id: 'e2', label: 'Scan nodes', command: 'bago audit scan --nodes', kind: 'command' },
      { id: 'e3', label: 'Scan pieces', command: 'bago audit scan --pieces', kind: 'command' },
      { id: 'e4', label: 'Generate report', command: 'bago audit report --html', kind: 'command', dependsOn: ['e1', 'e2', 'e3'] },
    ],
  },
]

export function computePlanSteps(steps) {
  const byId = new Map(steps.map((s) => [s.id, s]))
  const dependents = new Map(steps.map((s) => [s.id, []]))
  steps.forEach((s) => {
    if (s.dependsOn) {
      s.dependsOn.forEach((dep) => {
        dependents.get(dep).push(s.id)
      })
    }
  })
  return { byId, dependents }
}
