// Datos de demostración para el BAGO Control Plane.
// En producción estos valores vendrían de bago node status --json, releases, ledger, etc.

export const DEMO_INSTALLATIONS = [
  {
    id: 'inst-A',
    name: 'inst-A · Producción',
    path: 'X:\\bago_fw\\BAGO_v4',
    version: '4.6.0',
    mode: 'stable',
    supervisor: 'alive',
    pieces: 12,
    lastSync: 'ahora',
    policy: 'safe-autonomy',
  },
  {
    id: 'BAGO-BETA',
    name: 'BAGO-BETA',
    path: 'D:\\sandbox\\bago-beta',
    version: '4.7.0-b2',
    mode: 'beta',
    supervisor: 'alive',
    pieces: 9,
    lastSync: '2 min',
    policy: 'staged',
  },
  {
    id: 'BAGO-SHADOW',
    name: 'BAGO-SHADOW',
    path: 'E:\\labs\\bago-shadow',
    version: '4.6.1-rc',
    mode: 'shadow',
    supervisor: 'alive',
    pieces: 7,
    lastSync: '7 min',
    policy: 'isolated',
  },
  {
    id: 'legacy-42',
    name: 'legacy-42',
    path: 'C:\\archive\\bago-4.2',
    version: '4.2.0',
    mode: 'locked',
    supervisor: 'dead',
    pieces: 4,
    lastSync: '14 días',
    policy: 'frozen',
  },
]

export const DEMO_PIECES = [
  { id: 'codex-cli', type: 'Tool', desc: 'Puente CLI para ejecución asistida, restringida por políticas locales.' },
  { id: 'github-repo', type: 'Connector', desc: 'Conector a repositorios con modo read-only o writable por instalación.' },
  { id: 'bago-docs', type: 'Knowledge', desc: 'Base documental canónica con hashes y estado de indexación local.' },
  { id: 'orchestrator', type: 'Agent', desc: 'Clasifica tareas, asigna especialistas y revisa coherencia del conjunto.' },
  { id: 'release-auditor', type: 'Skill', desc: 'Valida bundle, checksum, contrato de release y evidencia generada.' },
  { id: 'voice-output', type: 'Tool', desc: 'Normaliza respuestas para locución completa y lectura continua.' },
]

export const DEMO_RELEASES = [
  { channel: 'Stable', version: 'BAGO 4.6.1', desc: 'Corrección del manager, actualización del ledger y validación de conectores.', bundle: '182 MB', sha: '8d7f…2ac1', signed: true },
  { channel: 'Beta', version: 'BAGO 4.7.0-b2', desc: 'Nuevo Patchbay, inspector contextual y jobs no bloqueantes.', bundle: '191 MB', sha: '4ab1…09ef', signed: false },
  { channel: 'Legacy', version: 'BAGO 4.5.2', desc: 'Release estable anterior conservada para recuperación controlada.', bundle: '176 MB', sha: '12aa…17c4', signed: false },
]

export const DEMO_AUDIT = [
  { status: 'ok', action: 'connector.attach', detail: 'Codex CLI conectado a inst-A en modo connected', time: '02:51:14', body: 'Claim: la pieza puede leer y escribir solo dentro del scope permitido.\nComando: bago connector attach inst-A codex-cli --mode connected\nEvidencia: policy check passed · route probe passed · ledger hash 9bc2…ef11\nConclusión: operación aplicada y reversible.' },
  { status: 'ok', action: 'release.verify', detail: 'Bundle 4.6.1 coincide con el checksum publicado', time: '02:46:02', body: 'Claim: el artefacto no fue alterado.\nEvidencia: SHA256 local coincide con manifiesto firmado.' },
  { status: 'warn', action: 'policy.switch', detail: 'BAGO-BETA cambió a shadow para prueba aislada', time: '02:39:44', body: 'Claim: la instalación no puede afectar producción.\nEvidencia: write routes disabled · isolated cache enabled.' },
  { status: 'cyan', action: 'node.refresh', detail: 'Topología reconstruida desde estado local', time: '02:35:09', body: 'Fuente: bago node status --json\nResultado: 4 instalaciones, 28 piezas, 32 conectores.' },
]

export const DEMO_HEALTH = [
  { label: 'Supervisor', value: 'Operativo', percent: 98, note: 'Latencia local 14 ms. Sin reinicios inesperados.', badge: null },
  { label: 'Instalaciones', value: '3 de 4 OK', percent: 75, note: 'La instalación legacy-42 está bloqueada y sin supervisor.', badge: { text: '1 legacy', variant: 'warn' } },
  { label: 'Conectores', value: '32 activos', percent: 100, note: 'Todos los probes de routing y permisos han pasado.', badge: { text: 'Sin errores', variant: 'ok' } },
  { label: 'Claims', value: '18 validados', percent: 100, note: 'No hay claims pendientes ni evidencia incompleta.', badge: { text: '100%', variant: 'ok' } },
  { label: 'Runtime', value: 'Local-first', percent: 92, note: 'Caché local válida y backend API disponible.', badge: { text: 'Offline ready', variant: 'cyan' } },
  { label: 'Compatibilidad', value: 'Windows x64', percent: 96, note: 'Electron bridge, Python y Git detectados.', badge: { text: 'Soportado', variant: 'ok' } },
]

export const DEMO_NODES = [
  { id: 'inst-A', label: 'inst-A', sub: 'Installation · stable', left: '50%', top: '50%', core: true },
  { id: 'Codex CLI', label: 'Codex CLI', sub: 'Tool · connected', left: '24%', top: '23%' },
  { id: 'PieceStore', label: 'PieceStore', sub: 'Registry · connected', left: '76%', top: '21%' },
  { id: 'Knowledge', label: 'Knowledge', sub: 'Store · connected', left: '19%', top: '68%' },
  { id: 'GitHub', label: 'GitHub', sub: 'Repo · read-only', left: '79%', top: '70%' },
  { id: 'Policy Engine', label: 'Policy Engine', sub: 'Agent · locked', left: '50%', top: '13%' },
]

export const DEMO_PATCH_ROWS = [
  {
    installationId: 'inst-A',
    installationSub: 'stable · 4.6.0',
    cells: { 'Codex CLI': 'connected', 'Copilot': 'readonly', 'Registry': 'connected', 'Knowledge': 'connected', 'GitHub': 'readonly', 'Voice': 'shadow' },
  },
  {
    installationId: 'BAGO-BETA',
    installationSub: 'beta · 4.7.0-b2',
    cells: { 'Codex CLI': 'shadow', 'Copilot': 'shadow', 'Registry': 'connected', 'Knowledge': 'readonly', 'GitHub': 'detached', 'Voice': 'connected' },
  },
  {
    installationId: 'BAGO-SHADOW',
    installationSub: 'shadow · lab',
    cells: { 'Codex CLI': 'shadow', 'Copilot': 'detached', 'Registry': 'shadow', 'Knowledge': 'shadow', 'GitHub': 'readonly', 'Voice': 'detached' },
  },
  {
    installationId: 'legacy-42',
    installationSub: 'locked · archive',
    cells: { 'Codex CLI': 'locked', 'Copilot': 'locked', 'Registry': 'locked', 'Knowledge': 'readonly', 'GitHub': 'readonly', 'Voice': 'detached' },
  },
]

export const DEMO_KPI = {
  installations: { value: '4', sub: '3 operativas · 1 shadow' },
  pieces: { value: '28', sub: '21 conectadas · 7 disponibles' },
  release: { value: '4.6.0', sub: 'Canal stable · firmado' },
  audit: { value: '100%', sub: '18 claims validados' },
}

export const DEMO_JOBS = [
  { title: 'Index knowledge', progress: '72%', status: 'inst-A · background', color: 'cyan' },
  { title: 'Verify 4.6.1', progress: 'completo', status: 'checksum + signature', color: 'ok' },
]

export const DEMO_RECENT_EVENTS = [
  { title: 'connector.attach · Codex CLI', sub: 'inst-A · claim validado', time: '02:51', color: 'brand' },
  { title: 'release.verify · 4.6.1', sub: 'SHA256 coincide', time: '02:46', color: 'cyan' },
  { title: 'policy.switch · shadow', sub: 'BAGO-BETA · reversible', time: '02:39', color: 'warn' },
]

export const DEMO_AVAILABLE_RELEASES = [
  { version: '4.6.1', meta: 'Stable · checksum validado', variant: 'ok' },
  { version: '4.7.0-b2', meta: 'Beta · manager renovado', variant: 'warn' },
  { version: '4.5.2', meta: 'Rollback firmado', variant: 'neutral' },
]
