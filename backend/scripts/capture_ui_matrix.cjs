const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'ui-react', 'dist');
const OUT = path.join(ROOT, 'output', 'playwright', 'ui-matrix', new Date().toISOString().replace(/[:.]/g, '-'));

const MODULES = [
  'overview',
  'workspace',
  'files',
  'context',
  'model',
  'tools',
  'roadmap',
  'reflexive',
  'pipeline',
  'evidence',
  'sessions',
  'system',
  'console',
];

function safeName(value) {
  return String(value || 'screen')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
    .slice(0, 140);
}

function contentType(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === '.html') return 'text/html; charset=utf-8';
  if (ext === '.js') return 'text/javascript; charset=utf-8';
  if (ext === '.css') return 'text/css; charset=utf-8';
  if (ext === '.svg') return 'image/svg+xml';
  if (ext === '.png') return 'image/png';
  if (ext === '.ico') return 'image/x-icon';
  return 'application/octet-stream';
}

function startStaticServer() {
  if (!fs.existsSync(DIST)) {
    throw new Error(`No existe ${DIST}. Ejecuta npm run manager:build-ui antes de capturar.`);
  }

  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent(new URL(req.url, 'http://127.0.0.1').pathname);
    const candidate = path.normalize(path.join(DIST, urlPath === '/' ? 'index.html' : urlPath));
    const target = candidate.startsWith(DIST) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()
      ? candidate
      : path.join(DIST, 'index.html');

    res.writeHead(200, { 'Content-Type': contentType(target) });
    fs.createReadStream(target).pipe(res);
  });

  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve({ server, url: `http://127.0.0.1:${server.address().port}` }));
  });
}

function action(command_id, label, emphasis = 'normal') {
  return {
    command_id,
    label,
    description: `Accion de prueba para ${label}`,
    emphasis,
    enabled: true,
    modifies_state: emphasis !== 'normal',
  };
}

function center(id, status = 'confirmed') {
  const entityPath = path.join(ROOT, '.gabo', id);
  return {
    center_id: id,
    state_revision: 'matrix-1',
    status,
    summary: `${id} operativo con datos sinteticos de captura`,
    active_entity: {
      id,
      path: entityPath,
      authority: 'backend-simulado-playwright',
    },
    metrics: [
      { label: 'estado', value: status, classification: 'state' },
      { label: 'items', value: 4, classification: 'count' },
      { label: 'revision', value: 'matrix-1', classification: 'trace' },
    ],
    items: [
      { id: `${id}-primary`, label: `${id} principal`, description: 'Elemento visible para auditoria UI', status },
      { id: `${id}-warning`, label: `${id} aviso`, description: 'Elemento con estado degradado', status: 'degraded' },
      { id: `${id}-blocked`, label: `${id} bloqueado`, description: 'Elemento bloqueado para contraste', status: 'blocked' },
      { id: `${id}-done`, label: `${id} cerrado`, description: 'Elemento confirmado', status: 'done' },
    ],
    recommended_actions: [
      action(`${id}.inspect`, `Inspeccionar ${id}`, 'primary'),
      action(`${id}.validate`, `Validar ${id}`),
    ],
    available_actions: [
      action(`${id}.open`, `Abrir ${id}`),
      action(`${id}.export`, `Exportar ${id}`),
    ],
    blocked_actions: [
      {
        ...action(`${id}.danger`, `Bloqueado ${id}`, 'danger'),
        enabled: false,
        blocked_reason: 'Bloqueado en matriz de captura',
      },
    ],
    recent_activity: [
      { id: `${id}-act-1`, label: `${id} actualizado`, status: 'done', created_at: '2026-06-29T10:00:00Z' },
    ],
    evidence_refs: [
      { id: `${id}-evidence`, path: `output/playwright/${id}.png`, kind: 'screenshot' },
    ],
    warnings: [
      { id: `${id}-warn`, label: `${id} requiere verificacion visual`, status: 'degraded' },
    ],
    detail: {
      selector: id,
      capture: true,
      nested: { foo: 'bar', count: 3 },
    },
  };
}

function sampleSnapshot() {
  const centers = Object.fromEntries(MODULES.map((id) => [id, center(id, id === 'pipeline' ? 'running' : 'confirmed')]));
  return {
    contract_version: 'bago.ui/v1',
    state_revision: 'matrix-1',
    source_revision: 'capture-ui-matrix',
    generated_at: '2026-06-29T10:00:00Z',
    connection: { status: 'confirmed', backend_version: 'playwright-matrix', bridge: 'route-intercept' },
    authorities: {
      framework_version: '4.8',
      framework_root: ROOT,
      project_root: ROOT,
      workspace_id: 'BAGO-MATRIX',
      workspace_root: path.join(ROOT, '.gabo'),
      workspace_scope_root: ROOT,
      session_id: 'session-matrix',
      context_revision: 'matrix-1',
    },
    task: {
      status: 'confirmed',
      objective: 'BAGO UI Matrix Capture',
      decisions: ['Chat como pestana', 'Manager como menu', 'Backend autoridad'],
      restrictions: ['No depender del backend real para screenshots'],
      next_step: 'Validar visualmente las capturas',
    },
    session: { status: 'confirmed', session_id: 'session-matrix', persisted: true, linked: true },
    workspace: { status: 'confirmed', state: 'linked', manifest_status: 'confirmed', index_status: 'confirmed' },
    context: {
      status: 'confirmed',
      configured_context: 128000,
      occupied_context: 42000,
      available_context: 86000,
      reserve: 12000,
      limiting_factor: 'ui-matrix',
      last_receipt_id: 'receipt-matrix',
    },
    model: {
      status: 'confirmed',
      provider: 'local',
      adapter: 'ollama',
      runtime: 'desktop',
      configured_model: 'bago-auto',
      effective_model: 'bago-auto',
    },
    system: { status: 'confirmed', operating_mode: 'manager', pipeline_status: 'running' },
    roadmap: {
      status: 'confirmed',
      summary: 'Tres iteraciones visibles',
      current_iteration: 'iteracion-3',
      roadmap_version: 'matrix',
      iterations: [
        { id: 'iteracion-1', label: 'Instalador', status: 'done' },
        { id: 'iteracion-2', label: 'Tabs chat/menu', status: 'done' },
        { id: 'iteracion-3', label: 'Controles hardware', status: 'running' },
      ],
    },
    chat: {
      status: 'confirmed',
      enabled: true,
      messages: [
        { id: 'm1', role: 'system', content: 'Snapshot sintetico para capturas UI.', created_at: '2026-06-29T10:00:00Z' },
        { id: 'm2', role: 'user', content: 'Captura todas las pantallas y desplegables.', created_at: '2026-06-29T10:01:00Z' },
        { id: 'm3', role: 'assistant', content: 'Matriz lista para validacion visual.', created_at: '2026-06-29T10:02:00Z' },
      ],
    },
    centers,
    menu: {
      recommended_actions: [action('status', 'Estado', 'primary'), action('roadmap', 'Roadmap')],
      available_actions: MODULES.map((id) => action(`${id}.open`, `Abrir ${id}`)),
    },
    pipeline: {
      status: 'running',
      execution_id: 'exec-matrix',
      steps: [
        { id: 'build', label: 'Build UI', status: 'done' },
        { id: 'capture', label: 'Capturas', status: 'running' },
        { id: 'manifest', label: 'Manifiesto', status: 'pending' },
      ],
    },
    recent_activity: [
      { id: 'activity-1', role: 'tool', content: 'manager:build-ui OK', created_at: '2026-06-29T10:03:00Z' },
      { id: 'activity-2', role: 'tool', content: 'capture_ui_matrix arrancado', created_at: '2026-06-29T10:04:00Z' },
    ],
  };
}

async function installApiRoutes(page) {
  const snapshot = sampleSnapshot();

  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathName = url.pathname;
    const corsHeaders = {
      'Access-Control-Allow-Origin': request.headers().origin || `${url.protocol}//${url.host}`,
      'Access-Control-Allow-Credentials': 'true',
      'Access-Control-Allow-Headers': 'content-type, accept',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    };
    const json = (body) => ({
      status: 200,
      contentType: 'application/json',
      headers: corsHeaders,
      body: JSON.stringify(body),
    });
    if (request.method() === 'OPTIONS') {
      await route.fulfill({ status: 204, headers: corsHeaders, body: '' });
      return;
    }
    if (pathName === '/api/v1/ui/bootstrap' || pathName === '/status' || pathName === '/session' || pathName === '/history' || pathName === '/providers' || pathName === '/menu') {
      await route.fulfill(json(snapshot));
      return;
    }
    if (pathName === '/api/v1/ui/command' || pathName === '/command') {
      await route.fulfill(json({
          request_id: `req-${Date.now()}`,
          execution_id: 'exec-matrix',
          status: 'done',
          state_revision: 'matrix-2',
          data: { directives: [], message: 'ok' },
          completed_at: new Date().toISOString(),
        }));
      return;
    }
    if (pathName === '/interpret') {
      await route.fulfill(json({ intent: 'ui.capture', confidence: 0.99, formalization: 'screenshot matrix' }));
      return;
    }
    if (pathName === '/interpret/history' || pathName === '/interpret/rules') {
      await route.fulfill(json({ items: [] }));
      return;
    }
    if (pathName === '/api/v1/ui/events') {
      await route.fulfill({ status: 204, headers: corsHeaders, body: '' });
      return;
    }
    await route.continue();
  });
}

async function capture(page, manifest, name, note = '') {
  await page.waitForTimeout(150);
  const file = `${safeName(`${manifest.viewport.name}-${name}`)}.png`;
  const target = path.join(OUT, file);
  await page.screenshot({ path: target, fullPage: true });
  manifest.captures.push({ name, viewport: manifest.viewport, file: path.relative(ROOT, target), note });
  console.log(`capture ${file}`);
}

async function clickByText(page, text) {
  const locator = page.getByRole('button', { name: new RegExp(`^${text}$`, 'i') }).first();
  if (await locator.count()) {
    await locator.click();
    return true;
  }
  return false;
}

async function selectValue(page, selector, value) {
  const locator = page.locator(selector).first();
  if (!(await locator.count())) return false;
  await locator.selectOption(value);
  return true;
}

async function cycleVisibleSelects(page, manifest, prefix) {
  const count = await page.locator('select:visible').count();
  if (!count) {
    manifest.nonCapturable.push({ scope: prefix, reason: 'No hay select visibles en este estado.' });
    return;
  }

  for (let index = 0; index < count; index += 1) {
    const currentCount = await page.locator('select:visible').count();
    if (index >= currentCount) break;
    const locator = page.locator('select:visible').nth(index);
    let meta;
    try {
      meta = await locator.evaluate((el) => ({
        id: el.id || '',
        name: el.name || '',
        label: el.getAttribute('aria-label') || '',
        options: Array.from(el.options).map((option) => ({ value: option.value, label: option.textContent.trim() })),
      }), { timeout: 3000 });
    } catch (error) {
      manifest.errors.push({ type: 'select-evaluate', scope: prefix, index, text: error.message });
      continue;
    }
    const selectName = safeName(meta.id || meta.name || meta.label || `select-${index}`);
    for (const option of meta.options) {
      try {
        const fresh = page.locator('select:visible').nth(index);
        await fresh.selectOption(option.value, { timeout: 3000 });
        await fresh.evaluate((el) => {
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }, { timeout: 3000 });
        await capture(page, manifest, `${prefix}-select-${selectName}-${safeName(option.label || option.value)}`, `select ${selectName}=${option.value}`);
      } catch (error) {
        manifest.errors.push({ type: 'select-option', scope: prefix, index, value: option.value, text: error.message });
        break;
      }
    }
  }
}

async function cycleVisibleRanges(page, manifest, prefix) {
  const count = await page.locator('input[type="range"]:visible').count();
  if (!count) {
    manifest.nonCapturable.push({ scope: prefix, reason: 'No hay faders/ranges visibles en este estado.' });
    return;
  }

  for (let index = 0; index < count; index += 1) {
    const currentCount = await page.locator('input[type="range"]:visible').count();
    if (index >= currentCount) break;
    const locator = page.locator('input[type="range"]:visible').nth(index);
    let meta;
    try {
      meta = await locator.evaluate((el) => {
        const min = Number(el.min || 0);
        const max = Number(el.max || 100);
        return {
          id: el.id || '',
          label: el.getAttribute('aria-label') || '',
          min,
          max,
          values: [min, Math.round((min + max) / 2), max],
        };
      }, { timeout: 3000 });
    } catch (error) {
      manifest.errors.push({ type: 'range-evaluate', scope: prefix, index, text: error.message });
      continue;
    }
    const rangeName = safeName(meta.id || meta.label || `range-${index}`);
    for (const value of meta.values) {
      try {
        const fresh = page.locator('input[type="range"]:visible').nth(index);
        await fresh.evaluate((el, next) => {
          el.value = String(next);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        }, value, { timeout: 3000 });
        await capture(page, manifest, `${prefix}-range-${rangeName}-${value}`, `range ${rangeName}=${value}`);
      } catch (error) {
        manifest.errors.push({ type: 'range-value', scope: prefix, index, value, text: error.message });
        break;
      }
    }
  }
}

async function runViewport(browser, baseUrl, viewport) {
  const context = await browser.newContext({ viewport: viewport.size, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  const manifest = {
    viewport,
    captures: [],
    errors: [],
    nonCapturable: [
      {
        scope: 'native-select-popup',
        reason: 'Chromium headless no expone la ventana nativa del desplegable; se captura cada opcion seleccionada.',
      },
    ],
  };

  page.on('console', (msg) => {
    if (msg.type() === 'error') manifest.errors.push({ type: 'console', text: msg.text() });
  });
  page.on('pageerror', (error) => manifest.errors.push({ type: 'pageerror', text: error.message }));

  await installApiRoutes(page);
  await page.addInitScript(() => {
    window.EventSource = undefined;
  });
  await page.goto(baseUrl, { waitUntil: 'networkidle' });
  await page.waitForSelector('.unified-app');
  await capture(page, manifest, '01-chat-inicial');
  await cycleVisibleSelects(page, manifest, 'chat');
  await cycleVisibleRanges(page, manifest, 'chat');

  await clickByText(page, 'Menú');
  await capture(page, manifest, '02-menu-inicial');
  await cycleVisibleRanges(page, manifest, 'menu');

  for (const moduleId of MODULES) {
    await selectValue(page, '#manager-rack-selector', moduleId);
    await capture(page, manifest, `module-${moduleId}`);
    await cycleVisibleSelects(page, manifest, `module-${moduleId}`);
    await cycleVisibleRanges(page, manifest, `module-${moduleId}`);
  }

  const toggleLabels = ['Rail', 'Chat', 'Menú'];
  for (const label of toggleLabels) {
    await clickByText(page, label);
    await capture(page, manifest, `toggle-${label}`);
  }

  const legacySelectors = [
    ['ContextPane', '.context-pane'],
    ['SessionKit', '.session-kit'],
    ['Dock', '.dock'],
    ['ManagerOverlay', '.manager-overlay'],
    ['ManagerInspector', '.manager-inspector'],
  ];
  for (const [name, selector] of legacySelectors) {
    if (!(await page.locator(selector).count())) {
      manifest.nonCapturable.push({ scope: name, reason: 'No esta montado por App.jsx en el flujo unificado actual.' });
    }
  }

  await context.close();
  return manifest;
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const { server, url } = await startStaticServer();
  const browser = await chromium.launch({ headless: true });
  const viewports = [
    { name: 'desktop', size: { width: 1440, height: 1000 } },
    { name: 'mobile', size: { width: 390, height: 844 } },
  ];
  const manifest = {
    generated_at: new Date().toISOString(),
    base_url: url,
    output_dir: path.relative(ROOT, OUT),
    viewports: [],
    totals: { captures: 0, errors: 0, nonCapturable: 0 },
  };

  try {
    for (const viewport of viewports) {
      const result = await runViewport(browser, url, viewport);
      manifest.viewports.push(result);
      manifest.totals.captures += result.captures.length;
      manifest.totals.errors += result.errors.length;
      manifest.totals.nonCapturable += result.nonCapturable.length;
    }
  } finally {
    await browser.close();
    server.close();
  }

  fs.writeFileSync(path.join(OUT, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  fs.writeFileSync(path.join(ROOT, 'output', 'playwright', 'ui-matrix', 'latest.txt'), OUT, 'utf8');
  console.log(JSON.stringify({ output_dir: OUT, totals: manifest.totals }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
