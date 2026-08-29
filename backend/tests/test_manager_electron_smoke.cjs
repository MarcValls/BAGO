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
function baseArgs(target) {
  const list = [target];
  const userData = String(process.env.BAGO_ELECTRON_USER_DATA_DIR || '').trim();
  if (userData) list.unshift('--user-data-dir=' + userData);
  return list;
}
  const app = await electron.launch({
    ...(executablePath ? { executablePath, args: baseArgs(executablePath) } : { args: baseArgs(ROOT) }),
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

    const sidebar = window.locator('.main-sidebar');
    const sidebarButton = (label) => sidebar.getByRole('button', { name: new RegExp(`^${label}\\b`) });
    const chatNav = sidebarButton('Chat');
    assert.strictEqual(await chatNav.count(), 0, 'Chat must remain inside Inicio, not as a duplicate destination');
    const homeNav = sidebarButton('Inicio');
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
    await window.waitForFunction(() => {
      const active = document.activeElement;
      return active instanceof HTMLElement
        && active.classList.contains('sidebar-item')
        && ((active.textContent || '').includes('Inicio') || (active.getAttribute('title') || '').startsWith('Inicio'));
    }, null, { timeout: 5000 });
    assert.strictEqual(await homeNav.evaluate((element) => document.activeElement === element), true);
    const modelSelector = window.getByRole('button', { name: 'Modelo de esta sesión', exact: true });
    const entryState = await window.waitForFunction(() => {
      const model = document.querySelector('[aria-label="Modelo de esta sesión"]');
      if (model instanceof HTMLButtonElement && model.offsetParent) return 'chat';
      const start = document.querySelector('.start-chat-path.is-primary');
      if (start instanceof HTMLButtonElement && start.offsetParent) return 'welcome';
      return '';
    }, null, { timeout: 120000 }).then((handle) => handle.jsonValue());
    const initialScopeConversationResponse = entryState === 'welcome'
      ? window.waitForResponse((response) => (
        new URL(response.url()).pathname === '/workspace/conversation'
        && response.request().method() === 'POST'
      ))
      : null;
    if (entryState === 'welcome') {
      await window.locator('.start-chat-path.is-primary').click();
    }
    try {
      await modelSelector.waitFor({ state: 'visible', timeout: 120000 });
    } catch (error) {
      const chatStartDiagnostic = await window.evaluate(() => ({
        activeSection: document.querySelector('.sidebar-item[aria-current="page"]')?.textContent || '',
        conversationError: document.querySelector('[role="alert"]')?.textContent || '',
        startButton: document.querySelector('.start-chat-path.is-primary')?.textContent || '',
        startDisabled: document.querySelector('.start-chat-path.is-primary') instanceof HTMLButtonElement
          ? document.querySelector('.start-chat-path.is-primary').disabled
          : false,
        visibleText: document.body.innerText.slice(0, 1600),
      }));
      console.error(JSON.stringify({ chatStartDiagnostic }));
      throw error;
    }
    if (initialScopeConversationResponse) {
      const initialScopeHttpResponse = await initialScopeConversationResponse;
      assert.strictEqual(initialScopeHttpResponse.status(), 200);
      assert.strictEqual((await initialScopeHttpResponse.json()).ok, true);
    }
    await modelSelector.click();
    const modelOptions = window.getByRole('listbox', { name: 'Modelos disponibles' }).getByRole('option');
    await window.waitForFunction(() => document.querySelectorAll('[role="listbox"][aria-label="Modelos disponibles"] [role="option"]').length >= 2, null, { timeout: 120000 });
    const modelState = await modelOptions.evaluateAll((options) => options.map((option, index) => ({
      index,
      unavailable: option.getAttribute('aria-disabled') === 'true',
      selected: option.getAttribute('aria-selected') === 'true',
      text: option.textContent || '',
    })));
    if (modelState.length < 2) {
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
    assert.ok(modelState.length >= 2, 'chat model selector has no router models');
    const candidate = modelState.find((option) => option.index > 0 && !option.unavailable);
    assert.ok(candidate, 'chat model selector has no alternate model');
    const automaticBeforeSelection = await window.evaluate(async () => (
      fetch('/router/session-model').then(async (response) => ({
        status: response.status,
        body: await response.json(),
      }))
    ));
    assert.strictEqual(automaticBeforeSelection.status, 200);
    assert.strictEqual(automaticBeforeSelection.body.ok, true);
    assert.strictEqual(automaticBeforeSelection.body.session_model, null);
    const modelSelectionResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/router/session-model'
      && response.request().method() === 'POST'
    ));
    await modelOptions.nth(candidate.index).click();
    const modelSelectionHttpResponse = await modelSelectionResponse;
    assert.strictEqual(modelSelectionHttpResponse.status(), 200);
    const modelSelectionPayload = await modelSelectionHttpResponse.json();
    assert.strictEqual(modelSelectionPayload.ok, true);
    assert.ok(modelSelectionPayload.session_model, `model selection POST did not persist: ${JSON.stringify(modelSelectionPayload)}`);
    const [selectedProvider, selectedModel] = modelSelectionPayload.session_model.split(/\/(.+)/);
    assert.strictEqual(modelSelectionPayload.effective_provider, selectedProvider);
    assert.strictEqual(modelSelectionPayload.effective_model, selectedModel);
    await window.getByRole('listbox', { name: 'Modelos disponibles' }).waitFor({ state: 'detached', timeout: 30000 });
    const persistedModelResponse = await window.evaluate(async () => (
      fetch('/router/session-model').then(async (response) => ({
        status: response.status,
        body: await response.json(),
      }))
    ));
    assert.strictEqual(persistedModelResponse.status, 200);
    assert.strictEqual(persistedModelResponse.body.ok, true);
    const persistedModel = persistedModelResponse.body.session_model;
    assert.strictEqual(persistedModel, modelSelectionPayload.session_model, `chat model selection was not persisted: ${JSON.stringify(persistedModelResponse)}`);
    assert.strictEqual(persistedModelResponse.body.effective_provider, selectedProvider);
    assert.strictEqual(persistedModelResponse.body.effective_model, selectedModel);
    await modelSelector.click();
    const automaticModelResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/router/session-model'
      && response.request().method() === 'POST'
    ));
    await window.getByRole('option', { name: /Automático/ }).click();
    const automaticModelHttpResponse = await automaticModelResponse;
    assert.strictEqual(automaticModelHttpResponse.status(), 200);
    const automaticModelPayload = await automaticModelHttpResponse.json();
    assert.strictEqual(automaticModelPayload.ok, true);
    assert.strictEqual(automaticModelPayload.session_model, null);
    assert.strictEqual(automaticModelPayload.effective_provider, automaticBeforeSelection.body.effective_provider);
    assert.strictEqual(automaticModelPayload.effective_model, automaticBeforeSelection.body.effective_model);
    await window.getByRole('listbox', { name: 'Modelos disponibles' }).waitFor({ state: 'detached', timeout: 30000 });
    await window.waitForFunction(async () => {
      const data = await fetch('/router/session-model').then((response) => response.json());
      return data.session_model === null;
    }, null, { timeout: 120000 });
    const restoredModel = await window.evaluate(async () => (
      fetch('/router/session-model').then((response) => response.json())
    ));
    assert.strictEqual(restoredModel.session_model, null);
    assert.strictEqual(restoredModel.effective_provider, automaticBeforeSelection.body.effective_provider);
    assert.strictEqual(restoredModel.effective_model, automaticBeforeSelection.body.effective_model);

    await dismissFirstRun();
    const chatTimeline = window.locator('.chat-timeline');
    await chatTimeline.waitFor({ state: 'visible', timeout: 30000 });
    await window.locator('#bago-chat-composer').waitFor({ state: 'visible', timeout: 30000 });
    await window.getByRole('button', { name: 'Modelo de esta sesión', exact: true }).waitFor({ state: 'visible', timeout: 30000 });
    await chatTimeline.evaluate((timeline) => {
      const probe = document.createElement('div');
      probe.dataset.smokeScrollProbe = 'true';
      probe.style.height = '2400px';
      timeline.insertBefore(probe, timeline.firstChild);
      timeline.scrollTop = 0;
    });
    await window.waitForFunction(() => {
      const timeline = document.querySelector('.chat-timeline');
      return timeline && timeline.scrollHeight > timeline.clientHeight;
    }, null, { timeout: 30000 });
    const scrollToEnd = window.getByRole('button', { name: 'Ir al final de la conversación', exact: true });
    const scrollToStart = window.getByRole('button', { name: 'Ir al inicio de la conversación', exact: true });
    await window.waitForFunction(() => {
      const button = document.querySelector('[aria-label="Ir al final de la conversación"]');
      return button instanceof HTMLButtonElement && !button.disabled;
    }, null, { timeout: 30000 });
    await scrollToEnd.click();
    await window.waitForFunction(() => {
      const timeline = document.querySelector('.chat-timeline');
      return timeline && timeline.scrollTop >= timeline.scrollHeight - timeline.clientHeight - 1;
    }, null, { timeout: 30000 });
    await scrollToStart.click();
    await window.waitForFunction(() => {
      const timeline = document.querySelector('.chat-timeline');
      return timeline && timeline.scrollTop <= 1;
    }, null, { timeout: 30000 });
    await chatTimeline.evaluate((timeline) => timeline.querySelector('[data-smoke-scroll-probe="true"]')?.remove());

    const initialConversations = await window.evaluate(async () => fetch('/conversations').then((response) => response.json()));
    const initialConversationId = initialConversations.active_conversation_id;
    const initialConversationCount = initialConversations.count;
    const createConversationResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/conversations'
      && response.request().method() === 'POST'
    ));
    const scopeConversationResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/workspace/conversation'
      && response.request().method() === 'POST'
    ));
    await window.getByRole('button', { name: 'Nuevo chat', exact: true }).click();
    const createdConversations = await (await createConversationResponse).json();
    const createdConversationId = createdConversations.active_conversation_id;
    assert.ok(createdConversationId.startsWith('chat-'), 'new conversation did not receive a canonical id');
    assert.notStrictEqual(createdConversationId, initialConversationId);
    assert.strictEqual(createdConversations.count, initialConversationCount + 1);
    const scopedConversationHttpResponse = await scopeConversationResponse;
    assert.strictEqual(scopedConversationHttpResponse.status(), 200);
    const scopedConversation = await scopedConversationHttpResponse.json();
    assert.strictEqual(scopedConversation.ok, true);
    assert.strictEqual(scopedConversation.conversation_id, createdConversationId);
    const conversationScreenshotPath = String(process.env.BAGO_ELECTRON_CONVERSATION_SCREENSHOT || '').trim();
    if (conversationScreenshotPath) {
      fs.mkdirSync(path.dirname(conversationScreenshotPath), { recursive: true });
      await window.screenshot({ path: conversationScreenshotPath });
    }

    const historyToggle = window.locator('.chat-conversation-menu summary');
    await historyToggle.click();
    const createdTitle = createdConversations.conversation.title;
    await window.locator('.chat-conversation-list article.is-active').getByRole('button', { name: `Renombrar ${createdTitle}`, exact: true }).click();
    const renamedTitle = 'Conversación smoke renombrada';
    await window.getByLabel('Título de conversación').fill(renamedTitle);
    const renameConversationResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/conversations'
      && response.request().method() === 'POST'
    ));
    await window.getByRole('button', { name: 'Guardar', exact: true }).click();
    const renamedConversations = await (await renameConversationResponse).json();
    assert.strictEqual(renamedConversations.conversation.title, renamedTitle);

    const initialConversation = renamedConversations.conversations.find((item) => item.conversation_id === initialConversationId);
    assert.ok(initialConversation, 'initial conversation disappeared after rename');
    const switchConversationResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/conversations'
      && response.request().method() === 'POST'
    ));
    await window.locator('.chat-conversation-list article', { hasText: initialConversation.title }).locator('.chat-conversation-open').click();
    const switchedConversations = await (await switchConversationResponse).json();
    assert.strictEqual(switchedConversations.active_conversation_id, initialConversationId);

    if (!await window.locator('.chat-conversation-menu').evaluate((details) => details.open)) {
      await historyToggle.click();
    }
    const archiveConversationResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/conversations'
      && response.request().method() === 'POST'
    ));
    await window.getByRole('button', { name: `Archivar ${renamedTitle}`, exact: true }).click();
    const archivedConversations = await (await archiveConversationResponse).json();
    assert.strictEqual(archivedConversations.active_conversation_id, initialConversationId);
    assert.strictEqual(archivedConversations.count, initialConversationCount);
    assert.strictEqual(archivedConversations.conversations.some((item) => item.conversation_id === createdConversationId), false);

    await dismissFirstRun();
    const contextNav = sidebarButton('Contexto');
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
      await modelSelector.waitFor({ state: 'visible', timeout: 120000 });
      assert.strictEqual(await homeNav.getAttribute('aria-current'), 'page');
    }

    await dismissFirstRun();
    const pipelineNav = sidebarButton('Pipeline');
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

    const operation = sidebarButton('Operaciones');
    assert.strictEqual(await operation.count(), 1);
    await operation.click();
    const operationNav = window.getByRole('navigation', { name: 'Herramientas de Operaciones' });
    await operationNav.waitFor({ state: 'visible', timeout: 30000 });
    const operationLabels = ['Proveedores', 'Runtime', 'Memoria', 'Visión', 'Configuración'];
    for (const label of operationLabels) {
      await operationNav.getByRole('button', { name: label, exact: true }).waitFor({ state: 'visible' });
    }
    const providerSurface = window.locator('.provider-center');
    await providerSurface.waitFor({ state: 'visible', timeout: 30000 });
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

    const autoConfigStatusResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/configure/auto/status'
      && response.request().method() === 'GET'
    ));
    const blacklistStatusResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/providers/blacklist'
      && response.request().method() === 'GET'
    ));
    const configurationButton = operationNav.getByRole('button', { name: 'Configuración', exact: true });
    await configurationButton.click();
    assert.strictEqual(await configurationButton.getAttribute('aria-current'), 'page');
    assert.strictEqual((await autoConfigStatusResponse).status(), 200);
    assert.strictEqual((await blacklistStatusResponse).status(), 200);

    const autoConfig = window.locator('.auto-config-card');
    await autoConfig.waitFor({ state: 'visible', timeout: 30000 });
    const autoConfigLabels = (await autoConfig.locator('button').allTextContents()).map((label) => label.trim());
    await autoConfig.getByRole('button', { name: 'Lanzar auto-test', exact: true }).waitFor({ state: 'visible' });
    const autoConfigScreenshotPath = String(process.env.BAGO_ELECTRON_AUTOCONFIG_SCREENSHOT || '').trim();
    if (autoConfigScreenshotPath) {
      fs.mkdirSync(path.dirname(autoConfigScreenshotPath), { recursive: true });
      await autoConfig.scrollIntoViewIfNeeded();
      await window.screenshot({ path: autoConfigScreenshotPath });
    }

    const blacklist = window.locator('.blacklist-card');
    await blacklist.waitFor({ state: 'visible', timeout: 30000 });
    const smokeModel = `smoke/blacklist-${Date.now()}`;
    await blacklist.getByLabel('Modelo para blacklist').fill(smokeModel);
    await blacklist.getByLabel('Motivo de blacklist').fill('Electron smoke temporal');
    const addBlacklistResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/providers/blacklist'
      && response.request().method() === 'POST'
    ));
    await blacklist.getByRole('button', { name: 'Añadir', exact: true }).click();
    const addBlacklistBody = await (await addBlacklistResponse).json();
    assert.ok(addBlacklistBody.models.includes(smokeModel));
    const blacklistItem = blacklist.locator('.blacklist-item').filter({ hasText: smokeModel });
    await blacklistItem.waitFor({ state: 'visible', timeout: 30000 });
    const removeBlacklistResponse = window.waitForResponse((response) => (
      new URL(response.url()).pathname === '/providers/blacklist'
      && response.request().method() === 'POST'
    ));
    await blacklistItem.getByRole('button', { name: 'Quitar', exact: true }).click();
    const removeBlacklistBody = await (await removeBlacklistResponse).json();
    assert.strictEqual(removeBlacklistBody.models.includes(smokeModel), false);
    await blacklistItem.waitFor({ state: 'detached', timeout: 30000 });
    const providerScreenshotPath = String(process.env.BAGO_ELECTRON_PROVIDER_SCREENSHOT || '').trim();
    if (providerScreenshotPath) {
      fs.mkdirSync(path.dirname(providerScreenshotPath), { recursive: true });
      await window.screenshot({ path: providerScreenshotPath });
    }

    const scrollAudit = await window.evaluate(() => (
      [...document.querySelectorAll('*')]
        .filter((element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return rect.width > 0 && rect.height > 0 && ['auto', 'scroll'].includes(style.overflowY);
        })
        .map((element) => ({
          className: element.className,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        }))
        .filter((surface) => surface.scrollWidth > surface.clientWidth + 1)
    ));
    assert.deepStrictEqual(scrollAudit, [], `Scrollable surfaces have horizontal overflow: ${JSON.stringify(scrollAudit)}`);

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
      operationViews: operationLabels.length,
      autoConfigControls: autoConfigLabels.length,
      blacklistRoundTrip: true,
      chatScrollRoundTrip: true,
      scrollAudit: 'no-horizontal-overflow',
      chatModelOptions: modelState.length,
      conversationRoundTrip: { initialConversationId, createdConversationId },
      contextSteps: contextFlow.steps,
      installed: Boolean(executablePath),
      consoleWarnings,
      httpErrors,
      screenshot: screenshotPath || null,
      autoConfigScreenshot: autoConfigScreenshotPath || null,
      conversationScreenshot: conversationScreenshotPath || null,
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


