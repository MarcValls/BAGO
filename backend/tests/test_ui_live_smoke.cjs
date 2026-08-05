const assert = require('assert');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'ui-react', 'dist');

function contentType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
  }[ext] || 'application/octet-stream';
}

function startServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const rawUrl = new URL(req.url || '/', 'http://127.0.0.1');
        let rel = decodeURIComponent(rawUrl.pathname);
        if (rel === '/' || rel === '') {
          rel = '/index.html';
        }
        const filePath = path.join(DIST, rel);
        if (!filePath.startsWith(DIST)) {
          res.statusCode = 403;
          res.end('forbidden');
          return;
        }
        const target = fs.existsSync(filePath) && fs.statSync(filePath).isFile()
          ? filePath
          : path.join(DIST, 'index.html');
        const body = fs.readFileSync(target);
        res.statusCode = 200;
        res.setHeader('Content-Type', contentType(target));
        res.end(body);
      } catch (error) {
        res.statusCode = 500;
        res.end('Internal Server Error');
      }
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

async function main() {
  assert.ok(fs.existsSync(path.join(DIST, 'index.html')), 'ui-react/dist/index.html missing');
  const server = await startServer();
  const port = server.address().port;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 } });
  await page.addInitScript(() => {
    localStorage.setItem('bago.first-run.v1.completed', 'true');
    sessionStorage.setItem('bago.start.chat-mode', 'open');
  });
  const consoleErrors = [];
  const consoleWarnings = [];
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
    if (message.type() === 'warning') consoleWarnings.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.message));
  try {
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });
    await page.locator('.app-root').waitFor();
    const contract = await page.evaluate(() => {
      const surface = document.querySelector('.surface-body');
      const ids = [...document.querySelectorAll('[id]')].map((el) => el.id);
      const scrollbar = surface ? getComputedStyle(surface, '::-webkit-scrollbar') : null;
      return {
        title: document.title,
        header: Boolean(document.querySelector('.global-header')),
        sidebar: Boolean(document.querySelector('.main-sidebar')),
        workspace: Boolean(document.querySelector('.workspace-shell')),
        surface: Boolean(surface),
        destinations: document.querySelectorAll('.sidebar-item').length,
        active: document.querySelectorAll('.sidebar-item[aria-current="page"]').length,
        scrollbarHidden: Boolean(scrollbar && (scrollbar.display === 'none' || scrollbar.width === '0px')),
        duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index),
      };
    });
    assert.equal(contract.title, 'BAGO Control Plane');
    assert.ok(contract.header && contract.sidebar && contract.workspace && contract.surface);
    assert.ok(contract.destinations >= 7);
    assert.equal(contract.active, 1);
    assert.ok(contract.scrollbarHidden);
    assert.deepEqual(contract.duplicateIds, []);

    const contrastRatios = await page.evaluate(() => {
      const rootStyle = getComputedStyle(document.documentElement);
      const parseHex = (hex) => [1, 3, 5].map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255);
      const luminance = (hex) => {
        const [red, green, blue] = parseHex(hex).map((value) => value <= 0.04045
          ? value / 12.92
          : ((value + 0.055) / 1.055) ** 2.4);
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
      };
      const ratio = (foreground, background) => {
        const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
        return (values[0] + 0.05) / (values[1] + 0.05);
      };
      const text = rootStyle.getPropertyValue('--text-3').trim();
      return Object.fromEntries(['--bg', '--bg-soft', '--surface', '--surface-2', '--surface-3'].map((token) => [
        token,
        ratio(text, rootStyle.getPropertyValue(token).trim()),
      ]));
    });
    for (const [surface, ratio] of Object.entries(contrastRatios)) {
      assert.ok(ratio >= 4.5, `--text-3 contrast on ${surface} is ${ratio.toFixed(2)}:1`);
    }

    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reducedMotion = await page.evaluate(() => {
      const probe = document.createElement('div');
      probe.style.animation = 'bago-pulse 1s infinite';
      probe.style.transition = 'opacity 1s ease';
      document.body.appendChild(probe);
      const style = getComputedStyle(probe);
      const result = {
        animationDuration: style.animationDuration,
        animationIterations: style.animationIterationCount,
        transitionDuration: style.transitionDuration,
      };
      probe.remove();
      return result;
    });
    assert.ok(Number.parseFloat(reducedMotion.animationDuration) <= 0.001, `reduced animation duration: ${reducedMotion.animationDuration}`);
    assert.equal(reducedMotion.animationIterations, '1');
    assert.ok(Number.parseFloat(reducedMotion.transitionDuration) <= 0.001, `reduced transition duration: ${reducedMotion.transitionDuration}`);
    await page.emulateMedia({ reducedMotion: 'no-preference' });

    const chatNav = page.locator('.sidebar-item').filter({ hasText: 'Chat' });
    assert.equal(await chatNav.count(), 0);
    const homeNav = page.locator('.sidebar-item').filter({ hasText: 'Inicio' });
    assert.equal(await homeNav.count(), 1);
    await homeNav.click();
    await page.locator('#bago-chat-model').waitFor({ state: 'visible' });
    assert.equal(await homeNav.getAttribute('aria-current'), 'page');
    const renderedText = await page.locator('body').innerText();
    assert.ok(!renderedText.includes("Unexpected token '<'"), 'raw JSON parser error leaked into the UI');
    assert.ok(
      renderedText.includes('La API de BAGO devolvió una respuesta no JSON.'),
      'offline backend error was not normalized'
    );
    await page.locator('[data-opening-state="show_blocked_state"]').waitFor({ state: 'visible' });

    const stateScreenshotDir = String(process.env.BAGO_UI_STATE_SCREENSHOT_DIR || '').trim();
    const renderState = async ({ name, status, session, workspace, expectedState, expectedText, viewport = { width: 1280, height: 860 }, assertResponsive = false, assertSystemTools = false, assertConversationControls = false }) => {
      const statePage = await browser.newPage({ viewport });
      const stateErrors = [];
      statePage.on('console', (message) => { if (message.type() === 'error') stateErrors.push(message.text()); });
      statePage.on('pageerror', (error) => stateErrors.push(error.message));
      await statePage.addInitScript(() => {
        localStorage.setItem('bago.first-run.v1.completed', 'true');
        sessionStorage.setItem('bago.start.chat-mode', 'open');
      });
      await statePage.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === '/api/v1/ui/bootstrap') {
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
            status,
            session,
            workspace,
            history: { conversation_id: 'main', messages: [] },
            conversations: {
              active_conversation_id: 'main',
              count: 2,
              conversations: [
                { conversation_id: 'main', title: 'Principal', message_count: 0, active: true },
                { conversation_id: 'chat-design', title: 'Diseño', message_count: 4, active: false },
              ],
            },
            sessions: {
              active_session_id: 'session-current',
              count: 2,
              archived_count: 1,
              sessions: [
                { session_id: 'session-current', title: 'Sesión actual', workspace_name: 'BAGO', message_count: 0, conversation_count: 2, active: true },
                { session_id: 'session-previous', title: 'Trabajo anterior', workspace_name: 'BAGO', message_count: 8, conversation_count: 1, active: false },
              ],
              archived_sessions: [
                { session_id: 'session-archived', title: 'Trabajo restaurable', workspace_name: 'BAGO', message_count: 12, conversation_count: 3, archived: true, archived_at: '2026-08-02T10:30:00Z' },
              ],
            },
            providers: { providers: [], catalog: [] },
            router_list: { entries: [] },
            router_policy: { entries: [], auto_switch: false },
          }) });
          return;
        }
        if (url.pathname === '/chat') {
          await new Promise((resolve) => setTimeout(resolve, 1500));
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, response: 'respuesta demorada', session_id: 'session-current', conversation_id: 'main' }) });
          return;
        }
        if (url.pathname === '/configure/auto/status') {
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
            ok: true,
            status: 'idle',
            last_job: { status: 'done', total_models: 3, tested_models: 3, generated_config: { default_model: 'ollama-local/qwen3' } },
          }) });
          return;
        }
        if (url.pathname === '/providers/blacklist') {
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, models: [], reasons: {}, path: 'C:/state/model_blacklist.json' }) });
          return;
        }
        if (url.pathname.startsWith('/api/') || ['/router/list', '/router/policy', '/router/session-model', '/files/read'].includes(url.pathname)) {
          await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, entries: [], messages: [], session_model: null }) });
          return;
        }
        await route.continue();
      });
      try {
        await statePage.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'domcontentloaded' });
        await statePage.locator('.app-root').waitFor({ state: 'visible', timeout: 30000 });
        if (expectedState) {
          const banner = statePage.locator(`[data-opening-state="${expectedState}"]`);
          await banner.waitFor({ state: 'visible', timeout: 30000 });
          assert.ok((await banner.innerText()).includes(expectedText), `${name} did not render ${expectedText}`);
        }
        if (assertResponsive) {
          const layout = await statePage.evaluate(() => {
            const visible = (selector) => {
              const element = document.querySelector(selector);
              return Boolean(element && element.getClientRects().length);
            };
            const app = document.querySelector('.app-root')?.getBoundingClientRect();
            return {
              viewportWidth: window.innerWidth,
              htmlScrollWidth: document.documentElement.scrollWidth,
              bodyScrollWidth: document.body.scrollWidth,
              appLeft: app?.left ?? -1,
              appRight: app?.right ?? Number.POSITIVE_INFINITY,
              headerVisible: visible('.global-header'),
              workspaceVisible: visible('.workspace-shell'),
              primaryControlVisible: [...document.querySelectorAll('button')].some((button) => button.getClientRects().length && !button.disabled),
              compactRailClean: window.innerWidth > 880 || [...document.querySelectorAll('.sidebar-section-title, .sidebar-item-label, .sidebar-item-shortcut, .sidebar-actions, .sidebar-status > div')]
                .every((element) => getComputedStyle(element).display === 'none'),
            };
          });
          assert.ok(layout.headerVisible && layout.workspaceVisible, `${name} lost the primary shell`);
          assert.ok(layout.primaryControlVisible, `${name} has no visible enabled control`);
          assert.ok(layout.compactRailClean, `${name} shows clipped compact-sidebar content`);
          assert.ok(layout.htmlScrollWidth <= layout.viewportWidth + 1, `${name} html overflow: ${layout.htmlScrollWidth}/${layout.viewportWidth}`);
          assert.ok(layout.bodyScrollWidth <= layout.viewportWidth + 1, `${name} body overflow: ${layout.bodyScrollWidth}/${layout.viewportWidth}`);
          assert.ok(layout.appLeft >= -1 && layout.appRight <= layout.viewportWidth + 1, `${name} app clipped: ${layout.appLeft}/${layout.appRight}`);
        }
        if (assertConversationControls) {
          const sessionSelect = statePage.getByLabel('Sesión activa');
          await sessionSelect.waitFor({ state: 'visible' });
          assert.strictEqual(await sessionSelect.locator('option').count(), 2, `${name} sessions are not visible`);
          await statePage.getByRole('button', { name: 'Nueva sesión', exact: true }).waitFor({ state: 'visible' });
          await statePage.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
          const manageSession = statePage.getByRole('dialog', { name: 'Gestionar sesión' });
          await manageSession.waitFor({ state: 'visible' });
          await manageSession.getByLabel('Buscar sesiones archivadas').fill('restaurable');
          await manageSession.getByLabel('Ordenar sesiones archivadas').selectOption('name');
          await manageSession.getByRole('button', { name: 'Restaurar Trabajo restaurable', exact: true }).waitFor({ state: 'visible' });
          await manageSession.getByRole('button', { name: 'Cancelar', exact: true }).click();
          const conversationSelect = statePage.getByLabel('Conversación activa');
          await conversationSelect.waitFor({ state: 'visible' });
          assert.strictEqual(await conversationSelect.locator('option').count(), 2, `${name} conversations are not visible`);
          await statePage.getByRole('button', { name: 'Nueva conversación', exact: true }).waitFor({ state: 'visible' });
          await statePage.locator('#bago-chat-composer').fill('prueba de respuesta pendiente');
          await statePage.getByRole('button', { name: 'Enviar', exact: true }).click();
          assert.strictEqual(await sessionSelect.isEnabled(), true, `${name} cannot switch sessions during an in-flight response`);
          await sessionSelect.selectOption('session-previous');
          const pendingConfirmation = statePage.getByRole('dialog', { name: 'Cambiar de sesión' });
          await pendingConfirmation.waitFor({ state: 'visible', timeout: 30000 });
          await pendingConfirmation.getByRole('button', { name: 'Cancelar', exact: true }).click();
          const conversationScreenshotPath = String(process.env.BAGO_UI_CONVERSATION_SCREENSHOT || '').trim();
          if (conversationScreenshotPath) {
            fs.mkdirSync(path.dirname(conversationScreenshotPath), { recursive: true });
            await statePage.screenshot({ path: conversationScreenshotPath, fullPage: false });
          }
        }
        if (assertSystemTools) {
          await statePage.keyboard.press('Control+7');
          await statePage.getByRole('tab', { name: 'Router', exact: true }).click();
          const autoConfig = statePage.locator('[data-system-tool="auto-config"]');
          await autoConfig.locator('summary').click();
          assert.strictEqual(await autoConfig.evaluate((element) => element.open), true, `${name} auto-config did not open`);
          await autoConfig.getByRole('button', { name: 'Refrescar', exact: true }).waitFor({ state: 'visible' });
          await autoConfig.getByRole('button', { name: /Lanzar auto-test|Cancelar prueba/ }).waitFor({ state: 'visible' });
          assert.strictEqual(await autoConfig.getByRole('button', { name: 'Aplicar propuesta', exact: true }).isEnabled(), true, `${name} persisted proposal cannot be applied`);

          await statePage.getByRole('tab', { name: 'Proveedores', exact: true }).click();
          const blacklist = statePage.locator('[data-system-tool="blacklist"]');
          await blacklist.locator('summary').click();
          assert.strictEqual(await blacklist.evaluate((element) => element.open), true, `${name} blacklist did not open`);
          await blacklist.getByLabel('Modelo para blacklist').waitFor({ state: 'visible' });
          await blacklist.getByRole('button', { name: 'Añadir', exact: true }).waitFor({ state: 'visible' });
          const toolLayout = await statePage.evaluate(() => ({
            viewportWidth: window.innerWidth,
            htmlScrollWidth: document.documentElement.scrollWidth,
            bodyScrollWidth: document.body.scrollWidth,
          }));
          assert.ok(toolLayout.htmlScrollWidth <= toolLayout.viewportWidth + 1, `${name} tool html overflow`);
          assert.ok(toolLayout.bodyScrollWidth <= toolLayout.viewportWidth + 1, `${name} tool body overflow`);
        }
        assert.deepEqual(stateErrors, [], `${name} console errors: ${stateErrors.join(' | ')}`);
        if (stateScreenshotDir) {
          fs.mkdirSync(stateScreenshotDir, { recursive: true });
          await statePage.screenshot({ path: path.join(stateScreenshotDir, `${name}.png`), fullPage: false });
        }
      } finally {
        await statePage.close();
      }
    };

    const linkedStatus = {
      framework_root: ROOT,
      framework_version: '4.8.1',
      project_root: 'C:/workspace',
      workspace_state_root: 'C:/workspace/.gabo',
      provider: 'copilot',
      model: 'gpt-5.4-mini',
      health: { ok: true },
    };
    await renderState({
      name: 'empty',
      status: { ...linkedStatus, project_root: '', workspace_state_root: '', workspace_state: { workspace_state: 'absent', binding_confirmed: false } },
      session: { session_id: 'state-empty', menu_state: { acciones_permitidas: ['workspace.init'], acciones_bloqueadas: ['chat.send'] } },
      workspace: { permissions: { canChat: false, canInitializeWorkspace: true } },
      expectedState: 'show_workspace_init',
      expectedText: 'No hay workspace activo',
    });
    await renderState({
      name: 'degraded',
      status: { ...linkedStatus, system_state: 'degraded', workspace_state: { workspace_state: 'linked_confirmed', binding_confirmed: true }, context_revision: 'ctx-1', last_receipt: { envelope_id: 'receipt-1' } },
      session: { session_id: 'state-degraded', menu_state: { acciones_permitidas: ['session.status', 'chat.send'], acciones_bloqueadas: [] } },
      workspace: { permissions: { canChat: true } },
      expectedState: 'show_recovery',
      expectedText: 'Se recomienda recuperar el estado',
    });
    await renderState({
      name: 'blocked',
      status: { ...linkedStatus, workspace_state: { workspace_state: 'invalid', binding_confirmed: false, binding_reason: 'manifest invalid' } },
      session: { session_id: 'state-blocked', menu_state: { acciones_permitidas: ['workspace.inspect', 'workspace.repair'], acciones_bloqueadas: ['chat.send', 'workspace.init'] } },
      workspace: { permissions: { canChat: false, canRepairWorkspace: true } },
      expectedState: 'show_workspace_repair',
      expectedText: 'El workspace necesita reparación',
    });

    const responsiveViewports = [
      { width: 320, height: 700 },
      { width: 640, height: 800 },
      { width: 820, height: 850 },
      { width: 1180, height: 900 },
    ];
    for (const viewport of responsiveViewports) {
      await renderState({
        name: `responsive-${viewport.width}`,
        status: { ...linkedStatus, workspace_state: { workspace_state: 'linked_confirmed', binding_confirmed: true }, context_revision: 'ctx-responsive', last_receipt: { envelope_id: 'receipt-responsive' } },
        session: { session_id: `responsive-${viewport.width}`, menu_state: { acciones_permitidas: ['chat.send', 'session.status'], acciones_bloqueadas: [] } },
        workspace: { permissions: { canChat: true } },
        viewport,
        assertResponsive: true,
        assertConversationControls: viewport.width === 640,
        assertSystemTools: viewport.width === 640,
      });
    }

    const screenshotPath = String(process.env.BAGO_UI_SMOKE_SCREENSHOT || '').trim();
    if (screenshotPath) {
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
      await page.screenshot({ path: screenshotPath, fullPage: false });
    }

    assert.deepEqual(consoleErrors, [], `browser console errors: ${consoleErrors.join(' | ')}`);
    console.log(JSON.stringify({
      ok: true,
      title: contract.title,
      destinations: contract.destinations,
      interaction: 'Inicio',
      stateScenarios: ['offline', 'empty', 'degraded', 'blocked'],
      responsiveViewports: responsiveViewports.map(({ width, height }) => `${width}x${height}`),
      systemTools: ['auto-config', 'blacklist'],
      contrastRatios,
      reducedMotion,
      consoleWarnings,
      screenshot: screenshotPath || null,
    }));
  } finally {
    await page.close().catch(() => {});
    await browser.close().catch(() => {});
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
