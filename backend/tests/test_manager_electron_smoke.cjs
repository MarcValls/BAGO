const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..');

async function main() {
  const executablePath = String(process.env.BAGO_MANAGER_EXE || '').trim();
  const smokeWorkspace = String(process.env.BAGO_MANAGER_SMOKE_WORKSPACE || '').trim()
    || path.join(os.tmpdir(), `bago-manager-smoke-${process.pid}`);
  fs.mkdirSync(smokeWorkspace, { recursive: true });
  const workspaceState = path.join(smokeWorkspace, '.gabo');
  fs.mkdirSync(workspaceState, { recursive: true });
  fs.writeFileSync(path.join(workspaceState, 'workspace.json'), JSON.stringify({
    workspace_id: `ws-smoke-${process.pid}`,
    project_root: smokeWorkspace,
    workspace_scope_root: smokeWorkspace,
  }, null, 2));
  fs.cpSync(
    path.join(ROOT, '.bago', 'context'),
    path.join(smokeWorkspace, '.bago', 'context'),
    { recursive: true }
  );
  const protectedFixtures = [
    path.join(ROOT, '.bago', 'context', 'context-packs.json'),
    path.join(ROOT, '.bago', 'context', 'context-tree.json'),
  ];
  const fixtureBaseline = new Map(protectedFixtures.map((file) => [file, fs.readFileSync(file)]));
  const app = await electron.launch({
    ...(executablePath ? { executablePath, args: [] } : { args: [ROOT] }),
    env: {
      ...process.env,
      BAGO_MANAGER_BASE_PATH: smokeWorkspace,
      BAGO_STATE_ROOT: path.join(smokeWorkspace, '.bago-test-state'),
      BAGO_MANAGER_AUTOMATION_TEST: '1',
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
  });

  try {
    const window = await app.firstWindow();
    const consoleErrors = [];
    const consoleWarnings = [];
    const httpErrors = [];
    window.on('console', (message) => {
      const location = message.location();
      const rendered = `${message.text()}${location.url ? ` @ ${location.url}` : ''}`;
      if (message.type() === 'error') consoleErrors.push(rendered);
      if (message.type() === 'warning') consoleWarnings.push(rendered);
    });
    window.on('pageerror', (error) => consoleErrors.push(error.message));
    window.on('response', (response) => {
      if (response.status() >= 400) httpErrors.push(`${response.status()} ${response.url()}`);
    });
    await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    await window.locator('.global-header').waitFor({ state: 'visible', timeout: 120000 });
    await window.locator('.main-sidebar').waitFor({ state: 'visible', timeout: 120000 });
    await window.locator('.workspace-shell').waitFor({ state: 'visible', timeout: 120000 });

    assert.strictEqual(await window.title(), 'BAGO Control Plane');
    const bridgeReady = await window.evaluate(() => Boolean(
      window.bagoElectron
      && typeof window.bagoElectron.managerHealth === 'function'
      && typeof window.bagoElectron.getChatUrl === 'function'
      && typeof window.bagoElectron.readInstallSelection === 'function'
    ));
    assert.strictEqual(bridgeReady, true, 'preload bridge missing');
    const managerHealth = await window.evaluate(() => window.bagoElectron.managerHealth());
    const resolvedRuntimeRoot = path.resolve(managerHealth.runtime_root);
    if (!executablePath) {
      assert.strictEqual(
        resolvedRuntimeRoot,
        ROOT,
        `development manager used a non-canonical runtime: ${managerHealth.runtime_root}`
      );
    } else {
      // Installed / packaged manager may resolve its own bundled runtime root
      // (e.g. app.asar.unpacked) instead of the development checkout.
      assert.ok(
        resolvedRuntimeRoot === ROOT || fs.existsSync(path.join(resolvedRuntimeRoot, 'bago_core', 'cli.py')),
        `packaged manager reported invalid runtime root: ${managerHealth.runtime_root}`
      );
    }

    const shell = await window.evaluate(() => {
      const surface = document.querySelector('.surface-body');
      const ids = [...document.querySelectorAll('[id]')].map((element) => element.id);
      const scrollbar = surface ? getComputedStyle(surface, '::-webkit-scrollbar') : null;
      return {
        destinations: document.querySelectorAll('.sidebar-item').length,
        active: document.querySelectorAll('.sidebar-item[aria-current="page"]').length,
        scrollbarHidden: Boolean(scrollbar && (scrollbar.display === 'none' || scrollbar.width === '0px')),
        duplicateIds: ids.filter((id, index) => ids.indexOf(id) !== index),
      };
    });
    assert.strictEqual(shell.destinations, 11);
    assert.strictEqual(shell.active, 1);
    assert.strictEqual(shell.scrollbarHidden, true);
    assert.deepStrictEqual(shell.duplicateIds, []);

    // For the packaged-manager smoke, verifying bridge + shell is sufficient.
    // The full chat/conversation/RL flow is covered by the dev-mode path and
    // the dedicated ui-live-smoke gate.
    if (executablePath) {
      console.log(JSON.stringify({
        ok: true,
        title: await window.title(),
        bridgeReady: true,
        runtimeRoot: managerHealth.runtime_root,
        workspace: smokeWorkspace,
        destinations: shell.destinations,
        installed: true,
        consoleWarnings,
        httpErrors,
        screenshot: null,
      }));
      return;
    }

    const dismissFirstRun = async () => {
      const close = window.getByRole('button', { name: 'Cerrar recorrido', exact: true });
      if (await close.count()) {
        const visible = await close.waitFor({ state: 'visible', timeout: 5000 }).then(() => true).catch(() => false);
        if (visible) await close.click();
      }
    };
    await dismissFirstRun();

    const chatNav = window.locator('.sidebar-item[title^="Chat ·"]');
    assert.strictEqual(await chatNav.count(), 0, 'Chat must remain inside Inicio, not as a duplicate destination');
    const homeNav = window.locator('.sidebar-item[title^="Inicio ·"]');
    assert.strictEqual(await homeNav.count(), 1);
    await homeNav.click();
    await dismissFirstRun();
    await homeNav.focus();
    await window.keyboard.press('Control+K');
    const commandDialog = window.getByRole('dialog', { name: 'Comandos rápidos' });
    await commandDialog.waitFor({ state: 'visible', timeout: 30000 });
    await window.waitForFunction(() => {
      const dialog = document.querySelector('[role="dialog"][aria-label="Comandos rápidos"]');
      return Boolean(dialog && dialog.contains(document.activeElement));
    });
    await window.keyboard.press('Shift+Tab');
    assert.strictEqual(await commandDialog.evaluate((dialog) => dialog.contains(document.activeElement)), true);
    await window.keyboard.press('Escape');
    await commandDialog.waitFor({ state: 'detached', timeout: 30000 });
    assert.strictEqual(await homeNav.evaluate((element) => document.activeElement === element), true);
    const modelSelect = window.locator('#bago-chat-model');
    const entryState = await window.waitForFunction(() => {
      const model = document.querySelector('#bago-chat-model');
      if (model instanceof HTMLSelectElement && model.offsetParent) return 'chat';
      const start = document.querySelector('.start-chat-path.is-primary');
      if (start instanceof HTMLButtonElement && start.offsetParent) return 'welcome';
      return '';
    }, null, { timeout: 120000 }).then((handle) => handle.jsonValue());
    if (entryState === 'welcome') {
      await window.locator('.start-chat-path.is-primary').click();
    }
    await modelSelect.waitFor({ state: 'visible', timeout: 120000 });
    await window.waitForFunction(() => {
      const select = document.querySelector('#bago-chat-model');
      return select instanceof HTMLSelectElement && select.options.length >= 2;
    }, null, { timeout: 120000 });
    const modelState = await window.evaluate(() => {
      const select = document.querySelector('#bago-chat-model');
      if (!(select instanceof HTMLSelectElement)) return { value: '', options: [] };
      return { value: select.value, options: [...select.options].map((option) => option.value) };
    });
    if (modelState.options.length < 2) {
      const routerDiagnostic = await window.evaluate(async () => ({
        policy: await fetch('/router/policy').then((response) => response.json()).catch((error) => ({ error: String(error) })),
        list: await fetch('/router/list').then((response) => response.json()).catch((error) => ({ error: String(error) })),
        bootstrap: await fetch('/api/v1/ui/bootstrap').then((response) => response.json()).then((data) => ({
          policyEntries: data.router_policy?.entries?.length,
          listEntries: data.router_list?.entries?.length,
          keys: Object.keys(data),
        })).catch((error) => ({ error: String(error) })),
      }));
      console.error(JSON.stringify({ modelState, routerDiagnostic }));
    }
    assert.ok(modelState.options.length >= 2, 'chat model selector has no router models');
    const candidate = modelState.options.find((value) => value && !value.startsWith('ollama-local/'))
      || modelState.options.find((value) => value && value !== modelState.value);
    assert.ok(candidate, 'chat model selector has no alternate model');
    await modelSelect.selectOption(candidate);
    await window.waitForFunction((expected) => {
      const select = document.querySelector('#bago-chat-model');
      return select instanceof HTMLSelectElement && select.value === expected && !select.disabled;
    }, candidate, { timeout: 120000 });
    assert.strictEqual(await modelSelect.inputValue(), candidate);
    const persistedModel = await window.evaluate(async () => (
      fetch('/router/session-model').then((response) => response.json()).then((data) => data.session_model)
    ));
    assert.strictEqual(persistedModel, candidate);
    await modelSelect.selectOption(modelState.value);
    await window.waitForFunction((expected) => {
      const select = document.querySelector('#bago-chat-model');
      return select instanceof HTMLSelectElement && select.value === expected && !select.disabled;
    }, modelState.value, { timeout: 120000 });

    const conversationSelect = window.getByLabel('Conversación activa');
    await conversationSelect.waitFor({ state: 'visible', timeout: 30000 });
    await dismissFirstRun();
    const initialConversationId = await conversationSelect.inputValue();
    const initialConversationCount = await conversationSelect.locator('option').count();
    await window.getByRole('button', { name: 'Nueva conversación', exact: true }).click();
    try {
      await window.waitForFunction(({ initialId, initialCount }) => {
        const select = document.querySelector('#bago-conversation-select');
        return select instanceof HTMLSelectElement && select.options.length === initialCount + 1 && select.value !== initialId && !select.disabled;
      }, { initialId: initialConversationId, initialCount: initialConversationCount }, { timeout: 30000 });
    } catch (error) {
      const conversationDiagnostic = await window.evaluate(async () => {
        const select = document.querySelector('#bago-conversation-select');
        return {
          select: select instanceof HTMLSelectElement ? { value: select.value, options: [...select.options].map((option) => option.value), disabled: select.disabled } : null,
          api: await fetch('/conversations').then((response) => response.json()).catch((reason) => ({ error: String(reason) })),
          body: document.body.innerText.slice(0, 1200),
        };
      });
      console.error(JSON.stringify({ conversationDiagnostic }));
      throw error;
    }
    const createdConversationId = await conversationSelect.inputValue();
    assert.ok(createdConversationId.startsWith('chat-'), 'new conversation did not receive a canonical id');
    const conversationScreenshotPath = String(process.env.BAGO_ELECTRON_CONVERSATION_SCREENSHOT || '').trim();
    if (conversationScreenshotPath) {
      fs.mkdirSync(path.dirname(conversationScreenshotPath), { recursive: true });
      await window.screenshot({ path: conversationScreenshotPath });
    }
    await conversationSelect.selectOption(initialConversationId);
    await window.waitForFunction((expected) => {
      const select = document.querySelector('#bago-conversation-select');
      return select instanceof HTMLSelectElement && select.value === expected && !select.disabled;
    }, initialConversationId, { timeout: 30000 });

    const sessionSelect = window.getByLabel('Sesión activa');
    await sessionSelect.waitFor({ state: 'visible', timeout: 30000 });
    const initialSessionId = await sessionSelect.inputValue();
    const initialSessionCount = await sessionSelect.locator('option').count();
    await window.getByRole('button', { name: 'Nueva sesión', exact: true }).click();
    await window.waitForFunction(({ initialId, initialCount }) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && select.options.length === initialCount + 1 && select.value !== initialId && !select.disabled;
    }, { initialId: initialSessionId, initialCount: initialSessionCount }, { timeout: 60000 });
    const createdSessionId = await sessionSelect.inputValue();
    const sessionScreenshotPath = String(process.env.BAGO_ELECTRON_SESSION_SCREENSHOT || '').trim();
    if (sessionScreenshotPath) {
      fs.mkdirSync(path.dirname(sessionScreenshotPath), { recursive: true });
      await window.screenshot({ path: sessionScreenshotPath });
    }
    await window.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    const sessionManagerDialog = window.getByRole('dialog', { name: 'Gestionar sesión' });
    await sessionManagerDialog.waitFor({ state: 'visible', timeout: 30000 });
    await sessionManagerDialog.getByLabel('Nombre de la sesión').fill('Sesión smoke renombrada');
    await sessionManagerDialog.getByRole('button', { name: 'Guardar nombre', exact: true }).click();
    await sessionManagerDialog.waitFor({ state: 'detached', timeout: 30000 });
    assert.ok((await sessionSelect.locator('option:checked').textContent()).includes('Sesión smoke renombrada'));
    await window.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    await window.getByRole('dialog', { name: 'Gestionar sesión' }).getByRole('button', { name: 'Archivar', exact: true }).click();
    const archiveConfirmation = window.getByRole('dialog', { name: 'Archivar sesión' });
    await archiveConfirmation.waitFor({ state: 'visible', timeout: 30000 });
    await archiveConfirmation.getByRole('button', { name: 'Archivar sesión', exact: true }).click();
    await window.waitForFunction((expected) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && select.value === expected.id && select.options.length === expected.count && !select.disabled;
    }, { id: initialSessionId, count: initialSessionCount }, { timeout: 60000 });
    await window.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    const archivedManagerDialog = window.getByRole('dialog', { name: 'Gestionar sesión' });
    await archivedManagerDialog.getByLabel('Buscar sesiones archivadas').fill('smoke renombrada');
    const archivedSessionScreenshotPath = String(process.env.BAGO_ELECTRON_ARCHIVED_SESSION_SCREENSHOT || '').trim();
    if (archivedSessionScreenshotPath) {
      fs.mkdirSync(path.dirname(archivedSessionScreenshotPath), { recursive: true });
      await window.waitForTimeout(250);
      await archivedManagerDialog.screenshot({ path: archivedSessionScreenshotPath });
    }
    await archivedManagerDialog.getByRole('button', { name: 'Restaurar Sesión smoke renombrada', exact: true }).click();
    await archivedManagerDialog.waitFor({ state: 'detached', timeout: 30000 });
    await window.waitForFunction((expected) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && select.value === expected.id && select.options.length === expected.count && !select.disabled;
    }, { id: createdSessionId, count: initialSessionCount + 1 }, { timeout: 60000 });

    await dismissFirstRun();
    const contextNav = window.locator('.sidebar-item[title^="Contexto ·"]');
    assert.strictEqual(await contextNav.count(), 1);
    await contextNav.click();
    await window.locator('.task-context-page').waitFor({ state: 'visible', timeout: 120000 });
    const contextFlow = await window.evaluate(() => ({
      steps: document.querySelectorAll('.context-flow-nav-item').length,
      activeSteps: document.querySelectorAll('.context-flow-nav-item[aria-current="step"]').length,
      stageHeadings: document.querySelectorAll('.context-flow-screen-header').length,
    }));
    assert.ok(contextFlow.steps === 0 || contextFlow.steps === 5);
    if (contextFlow.steps === 5) {
      assert.strictEqual(contextFlow.activeSteps, 1);
      assert.strictEqual(contextFlow.stageHeadings, 1);
    }
    const openConversation = window.getByRole('button', { name: 'Ver conversación', exact: true });
    if (await openConversation.count()) {
      await openConversation.click();
      await modelSelect.waitFor({ state: 'visible', timeout: 120000 });
      assert.strictEqual(await homeNav.getAttribute('aria-current'), 'page');
    }

    await dismissFirstRun();
    const pipelineNav = window.locator('.sidebar-item[title^="Pipeline ·"]');
    await pipelineNav.click();
    await window.locator('.pipeline-surface').click({ button: 'right' });
    const stopFlow = window.getByRole('menuitem', { name: 'Detener flujo', exact: true });
    await stopFlow.waitFor({ state: 'visible', timeout: 30000 });
    if (await stopFlow.isEnabled()) {
      await stopFlow.click();
      const confirmation = window.getByRole('dialog', { name: 'Detener flujo' });
      await confirmation.waitFor({ state: 'visible', timeout: 30000 });
      await window.waitForFunction(() => document.activeElement?.hasAttribute('data-autofocus'));
      assert.strictEqual(await window.evaluate(() => document.activeElement?.textContent?.trim()), 'Detener flujo');
      await window.keyboard.press('Tab');
      assert.strictEqual(await confirmation.evaluate((dialog) => dialog.contains(document.activeElement)), true);
      await window.keyboard.press('Shift+Tab');
      assert.strictEqual(await confirmation.evaluate((dialog) => dialog.contains(document.activeElement)), true);
      await window.keyboard.press('Escape');
      await confirmation.waitFor({ state: 'detached', timeout: 30000 });
    } else {
      await window.keyboard.press('Escape');
    }

    const operation = window.locator('.sidebar-item[title^="Operaciones ·"]');
    assert.strictEqual(await operation.count(), 1);
    await operation.click();
    await window.getByRole('tab', { name: 'Router', exact: true }).click();
    const autoConfig = window.locator('[data-system-tool="auto-config"]');
    await autoConfig.waitFor({ state: 'visible', timeout: 30000 });
    await autoConfig.locator('summary').click();
    assert.strictEqual(await autoConfig.evaluate((element) => element.open), true, 'Auto-config did not open');
    const autoConfigLabels = (await autoConfig.locator('button').allTextContents()).map((label) => label.trim());
    for (const label of ['Refrescar', 'Lanzar auto-test', 'Aplicar propuesta']) {
      await autoConfig.getByRole('button', { name: label, exact: true }).waitFor({ state: 'visible' });
    }
    await autoConfig.getByRole('button', { name: 'Refrescar', exact: true }).click();
    const autoConfigScreenshotPath = String(process.env.BAGO_ELECTRON_AUTOCONFIG_SCREENSHOT || '').trim();
    if (autoConfigScreenshotPath) {
      fs.mkdirSync(path.dirname(autoConfigScreenshotPath), { recursive: true });
      await autoConfig.scrollIntoViewIfNeeded();
      await window.screenshot({ path: autoConfigScreenshotPath });
    }

    await window.getByRole('tab', { name: 'Proveedores', exact: true }).click();
    const verify = window.getByRole('button', { name: 'Verificar 6 contratos cloud', exact: true });
    await verify.click();
    await window.getByText('6/6 offline · sin tráfico', { exact: true }).waitFor({ state: 'visible', timeout: 120000 });
    const providerSurface = window.locator('.system-tab-panel').filter({ hasText: 'Proveedores' });
    await providerSurface.waitFor({ state: 'visible', timeout: 30000 });
    assert.strictEqual(await providerSurface.locator('[style]').count(), 0, 'Provider surface contains inline styles');
    const providerLayout = await providerSurface.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return {
        left: rect.left,
        right: rect.right,
        viewportWidth: window.innerWidth,
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    });
    assert.ok(providerLayout.left >= -1 && providerLayout.right <= providerLayout.viewportWidth + 1, 'Provider surface is clipped');
    assert.ok(providerLayout.scrollWidth <= providerLayout.clientWidth + 1, 'Provider surface has horizontal overflow');
    const blacklist = window.locator('[data-system-tool="blacklist"]');
    await blacklist.locator('summary').click();
    const smokeModel = `smoke/blacklist-${Date.now()}`;
    await blacklist.getByLabel('Modelo para blacklist').fill(smokeModel);
    await blacklist.getByLabel('Motivo de blacklist').fill('Electron smoke temporal');
    await blacklist.getByRole('button', { name: 'Añadir', exact: true }).click();
    const blacklistItem = blacklist.locator('.system-tool-list li').filter({ hasText: smokeModel });
    await blacklistItem.waitFor({ state: 'visible', timeout: 30000 });
    await blacklistItem.getByRole('button', { name: `Quitar ${smokeModel} de la blacklist`, exact: true }).click();
    await blacklistItem.waitFor({ state: 'detached', timeout: 30000 });
    const providerScreenshotPath = String(process.env.BAGO_ELECTRON_PROVIDER_SCREENSHOT || '').trim();
    if (providerScreenshotPath) {
      fs.mkdirSync(path.dirname(providerScreenshotPath), { recursive: true });
      await window.screenshot({ path: providerScreenshotPath });
    }

    let rlReady = false;
    for (let attempt = 0; attempt < 3 && !rlReady; attempt += 1) {
      await window.getByRole('tab', { name: 'RL', exact: false }).click();
      try {
        await window.locator('.rl-actions').waitFor({ state: 'visible', timeout: 15000 });
        rlReady = true;
      } catch {}
    }
    assert.strictEqual(rlReady, true, 'RL panel did not remain active');
    const shadowControls = await window.locator('.rl-actions button').count();
    assert.strictEqual(shadowControls, 4);
    const rlLabels = await window.locator('.rl-actions button').allTextContents();
    for (const label of ['Actualizar', 'Entrenar BC', 'Evaluar política']) {
      assert.ok(rlLabels.includes(label), `RL control missing: ${label}`);
    }
    let rlActionDone = false;
    for (let attempt = 0; attempt < 3 && !rlActionDone; attempt += 1) {
      try {
        await window.getByRole('button', { name: 'Evaluar política', exact: true }).click({ force: true });
        await window.getByText('Resultado de la última acción', { exact: true }).waitFor({ state: 'visible', timeout: 20000 });
        rlActionDone = true;
      } catch {
        const operationAgain = window.locator('.sidebar-item[title^="Operaciones ·"]');
        await operationAgain.waitFor({ state: 'visible', timeout: 30000 });
        await operationAgain.click({ force: true });
        await window.getByRole('tab', { name: 'RL', exact: false }).click();
        await window.locator('.rl-actions').waitFor({ state: 'visible', timeout: 15000 });
      }
    }
    assert.strictEqual(rlActionDone, true, 'RL evaluation did not produce a visible result');

    const screenshotPath = String(process.env.BAGO_ELECTRON_SMOKE_SCREENSHOT || '').trim();
    if (screenshotPath) {
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
      await window.screenshot({ path: screenshotPath, fullPage: false });
    }
    assert.deepStrictEqual(httpErrors, [], `Electron HTTP errors: ${httpErrors.join(' | ')}`);
    assert.deepStrictEqual(consoleErrors, [], `Electron console errors: ${consoleErrors.join(' | ')}`);

    console.log(JSON.stringify({
      ok: true,
      title: await window.title(),
      bridgeReady,
      runtimeRoot: managerHealth.runtime_root,
      workspace: smokeWorkspace,
      destinations: shell.destinations,
      cloudContracts: '6/6',
      autoConfigControls: autoConfigLabels.length,
      blacklistRoundTrip: true,
      providerSurfaceInlineStyles: 0,
      rlControls: shadowControls,
      chatModelOptions: modelState.options.length,
      conversationRoundTrip: { initialConversationId, createdConversationId },
      sessionRoundTrip: { initialSessionId, createdSessionId },
      contextSteps: contextFlow.steps,
      installed: Boolean(executablePath),
      consoleWarnings,
      httpErrors,
      screenshot: screenshotPath || null,
      autoConfigScreenshot: autoConfigScreenshotPath || null,
      conversationScreenshot: conversationScreenshotPath || null,
      sessionScreenshot: sessionScreenshotPath || null,
      providerScreenshot: providerScreenshotPath || null,
    }));
  } finally {
    await app.close();
    for (const [file, expected] of fixtureBaseline) {
      assert.deepStrictEqual(fs.readFileSync(file), expected, `smoke mutated source fixture: ${file}`);
    }
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});


