#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execSync } from 'node:child_process'

const args = process.argv.slice(2)
const hasFlag = (flag) => args.includes(flag)
const getArgValue = (name) => {
  const idx = args.indexOf(name)
  if (idx === -1) return undefined
  return args[idx + 1]
}

const targetPathArg = getArgValue('--path')
const cwd = targetPathArg ? path.resolve(targetPathArg) : process.cwd()

if (!fs.existsSync(cwd) || !fs.statSync(cwd).isDirectory()) {
  console.error(`Ruta inválida para análisis: ${cwd}`)
  process.exit(1)
}

const format = (getArgValue('--format') ?? 'md').toLowerCase()
const outputFile = getArgValue('--output')
const maxTodos = Number(getArgValue('--max-todos') ?? 12)

const safeExec = (command) => {
  try {
    return execSync(command, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
    }).trim()
  } catch {
    return ''
  }
}

const isGitRepo = safeExec('git rev-parse --is-inside-work-tree') === 'true'
const hasRg = safeExec('command -v rg') !== ''

const severityOrder = {
  P1: 1,
  P2: 2,
  P3: 3,
}

let taskSeq = 1
const makeTask = ({ priority, title, description, evidence = [], commands = [] }) => ({
  id: `TASK-${String(taskSeq++).padStart(3, '0')}`,
  priority,
  title,
  description,
  evidence,
  commands,
})

const tasks = []
const context = {
  repoPath: cwd,
  generatedAt: new Date().toISOString(),
  git: {
    insideRepo: isGitRepo,
    stagedCount: 0,
    unstagedCount: 0,
    untrackedCount: 0,
    changedFiles: [],
  },
  todos: {
    total: 0,
    sampled: [],
  },
  workflows: {
    files: [],
    hasPushOrPr: false,
  },
  packageJson: {
    exists: false,
    missingScripts: [],
  },
}

const parseGitStatus = () => {
  const raw = safeExec('git status --porcelain=v1')
  if (!raw) return

  const lines = raw.split('\n').filter(Boolean)
  const files = new Set()

  for (const line of lines) {
    const match = line.match(/^(.{2})\s(.+)$/)
    if (match === null) continue
    const [indexStatus, workTreeStatus] = match[1].split('')
    const rawPath = match[2].trim()
    const normalizedPath = rawPath.includes(' -> ')
      ? rawPath.split(' -> ').at(-1)
      : rawPath

    if (indexStatus !== ' ' && indexStatus !== '?') context.git.stagedCount += 1
    if (workTreeStatus !== ' ') context.git.unstagedCount += 1
    if (indexStatus === '?') context.git.untrackedCount += 1

    if (normalizedPath) files.add(normalizedPath)
  }

  context.git.changedFiles = Array.from(files).sort()

  if (lines.length > 0) {
    tasks.push(makeTask({
      priority: lines.length > 20 ? 'P1' : 'P2',
      title: 'Revisar y agrupar cambios pendientes',
      description:
        'Hay cambios locales. Conviene separar en bloques pequeños y verificables antes de continuar.',
      evidence: [
        `Cambios detectados: ${lines.length}`,
        `Staged: ${context.git.stagedCount}, unstaged: ${context.git.unstagedCount}, untracked: ${context.git.untrackedCount}`,
      ],
      commands: [
        'git status --short',
        'git diff --name-only',
      ],
    }))
  }
}

const scanTodos = () => {
  let raw = ''
  if (hasRg) {
    raw = safeExec(
      "rg -n --hidden --glob '!node_modules' --glob '!.git' --glob '!dist' --glob '!release' --glob '!package-lock.json' '\\b(TODO|FIXME|HACK|XXX)\\b' .",
    )
  } else {
    raw = safeExec(
      "grep -RInE '\\b(TODO|FIXME|HACK|XXX)\\b' . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=release --exclude=package-lock.json",
    )
  }

  if (!raw) return

  const rows = raw
    .split('\n')
    .filter(Boolean)
    .filter((line) => !line.includes('scripts/propose-tasks.mjs'))
  if (rows.length === 0) return
  context.todos.total = rows.length
  context.todos.sampled = rows.slice(0, maxTodos)

  tasks.push(makeTask({
    priority: rows.length > 10 ? 'P1' : 'P2',
    title: 'Atacar deuda técnica marcada en comentarios',
    description:
      'Hay marcadores TODO/FIXME/HACK/XXX. Conviene convertirlos en tickets concretos y cerrar los críticos primero.',
    evidence: [
      `Total marcadores: ${rows.length}`,
      ...rows.slice(0, Math.min(5, rows.length)).map((line) => `- ${line}`),
    ],
    commands: [
      hasRg
        ? "rg -n '(TODO|FIXME|HACK|XXX)' src server scripts"
        : "grep -RInE '(TODO|FIXME|HACK|XXX)' src server scripts",
    ],
  }))
}

const inspectPackageJson = () => {
  const packageJsonPath = path.join(cwd, 'package.json')
  if (!fs.existsSync(packageJsonPath)) {
    tasks.push(makeTask({
      priority: 'P1',
      title: 'Inicializar package.json del repositorio',
      description:
        'No se encontró package.json en la raíz. Sin eso no hay scripts estándar para build/lint/test.',
      evidence: [packageJsonPath],
      commands: ['npm init -y'],
    }))
    return
  }

  context.packageJson.exists = true

  let parsed
  try {
    parsed = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'))
  } catch {
    tasks.push(makeTask({
      priority: 'P1',
      title: 'Corregir package.json inválido',
      description: 'El archivo package.json no es JSON válido.',
      evidence: [packageJsonPath],
      commands: ["node -e \"JSON.parse(require('fs').readFileSync('package.json','utf8'))\""],
    }))
    return
  }

  const scripts = parsed !== null && typeof parsed === 'object' ? parsed.scripts ?? {} : {}
  const requiredScripts = ['build', 'lint']
  const recommendedScripts = ['test']

  const missingRequired = requiredScripts.filter((name) => typeof scripts?.[name] !== 'string')
  const missingRecommended = recommendedScripts.filter((name) => typeof scripts?.[name] !== 'string')

  context.packageJson.missingScripts = [...missingRequired, ...missingRecommended]

  if (missingRequired.length > 0) {
    tasks.push(makeTask({
      priority: 'P1',
      title: 'Completar scripts obligatorios en package.json',
      description: 'Faltan scripts base para el flujo de calidad mínimo.',
      evidence: [
        `Scripts faltantes: ${missingRequired.join(', ')}`,
        packageJsonPath,
      ],
      commands: ['npm run build', 'npm run lint'],
    }))
  }

  if (missingRequired.length === 0 && missingRecommended.length > 0) {
    tasks.push(makeTask({
      priority: 'P2',
      title: 'Añadir script de tests',
      description: 'El repositorio no expone script test estándar en package.json.',
      evidence: [`Scripts faltantes: ${missingRecommended.join(', ')}`],
      commands: ['npm run test'],
    }))
  }
}

const inspectWorkflows = () => {
  const workflowsDir = path.join(cwd, '.github', 'workflows')
  if (!fs.existsSync(workflowsDir) || !fs.statSync(workflowsDir).isDirectory()) {
    tasks.push(makeTask({
      priority: 'P2',
      title: 'Configurar CI básico en GitHub Actions',
      description: 'No existe .github/workflows con validaciones automáticas.',
      evidence: [workflowsDir],
      commands: ['mkdir -p .github/workflows'],
    }))
    return
  }

  const files = fs.readdirSync(workflowsDir)
    .filter((name) => name.endsWith('.yml') || name.endsWith('.yaml'))
    .sort()

  context.workflows.files = files

  if (files.length === 0) {
    tasks.push(makeTask({
      priority: 'P2',
      title: 'Añadir primer workflow de CI',
      description: 'Hay carpeta de workflows pero sin archivos yml/yaml.',
      evidence: [workflowsDir],
      commands: ['touch .github/workflows/ci.yml'],
    }))
    return
  }

  const hasPushOrPr = files.some((name) => {
    const content = fs.readFileSync(path.join(workflowsDir, name), 'utf8')
    return /\bon:\s*[\s\S]*\b(push|pull_request)\b/m.test(content)
  })

  context.workflows.hasPushOrPr = hasPushOrPr

  if (!hasPushOrPr) {
    tasks.push(makeTask({
      priority: 'P2',
      title: 'Activar CI en push/pull_request',
      description: 'Los workflows actuales no parecen ejecutarse automáticamente en cambios de código.',
      evidence: files.map((f) => path.join('.github/workflows', f)),
      commands: ['npm run lint', 'npm run build'],
    }))
  }
}

const inspectLargeFiles = () => {
  const scanRoots = ['src', 'server', 'scripts']
  const candidates = []

  const walk = (dir) => {
    if (!fs.existsSync(dir)) return
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const fullPath = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        walk(fullPath)
        continue
      }
      if (!/\.(ts|tsx|js|mjs|jsx)$/.test(entry.name)) continue

      const content = fs.readFileSync(fullPath, 'utf8')
      const lines = content.split('\n').length
      if (lines >= 400) {
        candidates.push({ path: fullPath, lines })
      }
    }
  }

  for (const root of scanRoots) {
    walk(path.join(cwd, root))
  }

  const top = candidates
    .sort((a, b) => b.lines - a.lines)
    .slice(0, 5)

  if (top.length > 0) {
    tasks.push(makeTask({
      priority: 'P3',
      title: 'Considerar partición de archivos grandes',
      description: 'Hay archivos largos que podrían dificultar mantenimiento y revisión.',
      evidence: top.map((entry) => `${path.relative(cwd, entry.path)} (${entry.lines} líneas)`),
      commands: ['rg --files src server scripts'],
    }))
  }
}

if (isGitRepo) parseGitStatus()
scanTodos()
inspectPackageJson()
inspectWorkflows()
inspectLargeFiles()

if (tasks.length === 0) {
  tasks.push(makeTask({
    priority: 'P3',
    title: 'Mantener baseline',
    description: 'No se detectaron señales claras de deuda o gaps automáticos en este análisis rápido.',
    evidence: ['Sin cambios pendientes relevantes ni TODO/FIXME detectados.'],
    commands: ['npm run lint', 'npm run build'],
  }))
}

tasks.sort((a, b) => {
  const sa = severityOrder[a.priority] ?? 99
  const sb = severityOrder[b.priority] ?? 99
  if (sa !== sb) return sa - sb
  return a.id.localeCompare(b.id)
})

const payload = {
  meta: {
    generatedAt: context.generatedAt,
    repoPath: context.repoPath,
    format,
  },
  context,
  tasks,
}

const toMarkdown = () => {
  const lines = []
  lines.push('# Propuesta de tareas del repositorio')
  lines.push('')
  lines.push(`Generado: ${context.generatedAt}`)
  lines.push(`Ruta: ${context.repoPath}`)
  lines.push('')
  lines.push('## Resumen')
  lines.push('')
  lines.push(`- Repo git: ${context.git.insideRepo ? 'sí' : 'no'}`)
  lines.push(`- Cambios locales: ${context.git.changedFiles.length}`)
  lines.push(`- TODO/FIXME/HACK/XXX: ${context.todos.total}`)
  lines.push(`- package.json: ${context.packageJson.exists ? 'sí' : 'no'}`)
  lines.push(`- Workflows: ${context.workflows.files.length}`)
  lines.push('')
  lines.push('## Tareas')
  lines.push('')

  for (const task of tasks) {
    lines.push(`### ${task.id} · [${task.priority}] ${task.title}`)
    lines.push('')
    lines.push(task.description)
    lines.push('')

    if (task.evidence.length > 0) {
      lines.push('Evidencia:')
      for (const evidence of task.evidence) {
        lines.push(`- ${evidence}`)
      }
      lines.push('')
    }

    if (task.commands.length > 0) {
      lines.push('Comandos sugeridos:')
      for (const command of task.commands) {
        lines.push(`- \`${command}\``)
      }
      lines.push('')
    }
  }

  return lines.join('\n')
}

let output
if (format === 'json') {
  output = `${JSON.stringify(payload, null, 2)}\n`
} else {
  output = `${toMarkdown()}\n`
}

if (outputFile) {
  fs.writeFileSync(path.resolve(cwd, outputFile), output)
}

if (!hasFlag('--silent')) {
  process.stdout.write(output)
}
