// rpg-data.js — Transforma piezas BAGO en equipo de RPG.
// Cada pieza se mapea a un slot, rareza, atributos y habilidades para reducir
// carga cognitiva: el chat es el personaje y las piezas son su equipo.

export const RPG_SLOTS = {
  helm: { label: 'Casco', icon: 'helm', description: 'Visión, modelo y percepción del contexto.' },
  chest: { label: 'Pechera', icon: 'chest', description: 'Armadura principal: estabilidad del núcleo.' },
  hands: { label: 'Guantes', icon: 'hands', description: 'Herramientas y manipulación de artefactos.' },
  feet: { label: 'Botas', icon: 'feet', description: 'Velocidad de ejecución y respuesta.' },
  weapon: { label: 'Arma principal', icon: 'weapon', description: 'Provider/modelo de ataque principal.' },
  offhand: { label: 'Arma secundaria', icon: 'offhand', description: 'Provider/modelo de respaldo o fallback.' },
  ring1: { label: 'Anillo I', icon: 'ring', description: 'Accesorio especial: conector o skill.' },
  ring2: { label: 'Anillo II', icon: 'ring', description: 'Accesorio especial: skill o knowledge.' },
  amulet: { label: 'Amuleto', icon: 'amulet', description: 'Habilidad pasiva clave.' },
}

export const RARITIES = {
  common: { label: 'Común', color: '#9ca3af', glow: '0 0 0 transparent' },
  uncommon: { label: 'Poco común', color: '#22c55e', glow: '0 0 8px rgba(34,197,94,0.25)' },
  rare: { label: 'Raro', color: '#3b82f6', glow: '0 0 10px rgba(59,130,246,0.35)' },
  epic: { label: 'Épico', color: '#a855f7', glow: '0 0 12px rgba(168,85,247,0.45)' },
  legendary: { label: 'Legendario', color: '#f59e0b', glow: '0 0 16px rgba(245,158,11,0.55)' },
}

const TYPE_SLOT_MAP = {
  model: 'helm',
  translator: 'weapon',
  tool: 'hands',
  skill: 'amulet',
  agent: 'chest',
  knowledge: 'ring2',
  connector: 'ring1',
}

const TYPE_RARITY = {
  model: 'rare',
  translator: 'epic',
  tool: 'uncommon',
  skill: 'rare',
  agent: 'epic',
  knowledge: 'uncommon',
  connector: 'common',
}

const STAT_TEMPLATES = {
  model: { speed: 3, cost: 2, context: 5, stability: 4, security: 3 },
  translator: { speed: 4, cost: 3, context: 4, stability: 4, security: 4 },
  tool: { speed: 2, cost: 1, context: 2, stability: 5, security: 3 },
  skill: { speed: 2, cost: 1, context: 3, stability: 4, security: 5 },
  agent: { speed: 3, cost: 2, context: 5, stability: 3, security: 4 },
  knowledge: { speed: 1, cost: 1, context: 5, stability: 5, security: 3 },
  connector: { speed: 3, cost: 2, context: 3, stability: 4, security: 3 },
}

function hashSeeded(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

export function toRpgPiece(piece) {
  const type = (piece.type || piece.kind || 'connector').toLowerCase()
  const slot = TYPE_SLOT_MAP[type] || 'ring1'
  const rarityKey = TYPE_RARITY[type] || 'common'
  const baseStats = STAT_TEMPLATES[type] || STAT_TEMPLATES.connector
  const seed = hashSeeded(piece.id || piece.name || '')
  const variance = (n) => Math.max(1, Math.min(5, n + ((seed % 5) - 2)))
  const stats = {
    speed: variance(baseStats.speed),
    cost: variance(baseStats.cost),
    context: variance(baseStats.context),
    stability: variance(baseStats.stability),
    security: variance(baseStats.security),
  }

  const abilities = []
  if (type === 'tool') abilities.push('Ejecución asistida')
  if (type === 'skill') abilities.push('Validación contractual')
  if (type === 'agent') abilities.push('Orquestación de tareas')
  if (type === 'knowledge') abilities.push('Recuperación de memoria')
  if (type === 'connector') abilities.push('Sincronización externa')
  if (type === 'translator') abilities.push('Traducción de provider')
  if (type === 'model') abilities.push('Inferencia local')

  return {
    id: piece.id || piece.name || `piece-${seed}`,
    name: piece.id || piece.name || 'Pieza sin nombre',
    type,
    slot,
    rarity: rarityKey,
    rarityMeta: RARITIES[rarityKey],
    stats,
    abilities,
    description: piece.desc || piece.description || piece.status || 'Sin descripción',
    enabled: piece.enabled !== false,
    raw: piece,
  }
}

export function groupBySlot(pieces) {
  const map = Object.fromEntries(Object.keys(RPG_SLOTS).map((k) => [k, []]))
  pieces.forEach((p) => {
    const rpg = toRpgPiece(p)
    map[rpg.slot].push(rpg)
  })
  return map
}

export function defaultEquipped(pieces) {
  const bySlot = groupBySlot(pieces)
  const equipped = {}
  Object.keys(RPG_SLOTS).forEach((slot) => {
    const list = bySlot[slot]
    if (list.length) {
      // Preferir piezas habilitadas y de mayor rareza.
      equipped[slot] = [...list]
        .filter((p) => p.enabled)
        .sort((a, b) => Object.keys(RARITIES).indexOf(b.rarity) - Object.keys(RARITIES).indexOf(a.rarity))[0] || list[0]
    }
  })
  return equipped
}

export function computeGearScore(equipped) {
  const items = Object.values(equipped).filter(Boolean)
  if (!items.length) return 0
  const sum = items.reduce((acc, item) => {
    return acc + Object.values(item.stats).reduce((s, v) => s + v, 0)
  }, 0)
  return Math.round(sum / items.length)
}

// --- Datos de cadena de ejecución (rack) ---

export const RACK_MODULE_TYPES = {
  input: { label: 'Entrada', color: '#3b82f6', icon: 'in' },
  parse: { label: 'Parsear', color: '#8b5cf6', icon: 'parse' },
  think: { label: 'Pensar', color: '#a855f7', icon: 'brain' },
  tool: { label: 'Tool', color: '#f59e0b', icon: 'tool' },
  validate: { label: 'Validar', color: '#22c55e', icon: 'shield' },
  output: { label: 'Salida', color: '#10b981', icon: 'out' },
}

export const DEMO_RACK_CHAIN = [
  { id: 'in-1', type: 'input', label: 'Mensaje del usuario', command: 'read_user_input', dependsOn: [] },
  { id: 'parse-1', type: 'parse', label: 'Clasificar intención', command: 'intent_engine.classify', dependsOn: ['in-1'] },
  { id: 'think-1', type: 'think', label: 'Estrategia BAGO', command: 'orquestador.plan', dependsOn: ['parse-1'] },
  { id: 'tool-1', type: 'tool', label: 'Ejecutar herramienta', command: 'tool_registry.call', dependsOn: ['think-1'] },
  { id: 'validate-1', type: 'validate', label: 'Gate de seguridad', command: 'security_analyzer.check', dependsOn: ['tool-1'] },
  { id: 'out-1', type: 'output', label: 'Respuesta al chat', command: 'chat.reply', dependsOn: ['validate-1'] },
]
