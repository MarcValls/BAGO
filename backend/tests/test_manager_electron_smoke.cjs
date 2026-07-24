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
    assert.strictEqual(
      path.resolve(managerHealth.runtime_root),
      ROOT,
      `development manager used a non-canonical runtime: ${managerHealth.runtime_root}`
    );

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
    assert.ok(shell.destinations >= 8);
    assert.strictEqual(shell.active, 1);
    assert.strictEqual(shell.scrollbarHidden, true);
    assert.deepStrictEqual(shell.duplicateIds, []);

    const chatNav = window.locator('.sidebar-item').filter({ hasText: 'Chat' });
    assert.strictEqual(await chatNav.count(), 1);
    await chatNav.click();
    const modelSelect = window.locator('#bago-chat-model');
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

    const contextNav = window.locator('.sidebar-item').filter({ hasText: 'Contexto' });
    assert.strictEqual(await contextNav.count(), 1);
    await contextNav.click();
    await window.locator('.context-tree-module').waitFor({ state: 'visible', timeout: 120000 });
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

    const operation = window.locator('.sidebar-item').filter({ hasText: 'Operación' });
    assert.strictEqual(await operation.count(), 1);
    await operation.click();
    await window.getByRole('tab', { name: 'Proveedores', exact: true }).click();
    const verify = window.getByRole('button', { name: 'Verificar 6 contratos cloud', exact: true });
    await verify.click();
    await window.getByText('6/6 offline · sin tráfico', { exact: true }).waitFor({ state: 'visible', timeout: 120000 });

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
        const operationAgain = window.locator('.sidebar-item').filter({ hasText: 'Operación' });
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
      rlControls: shadowControls,
      chatModelOptions: modelState.options.length,
      contextSteps: contextFlow.steps,
      installed: Boolean(executablePath),
      consoleWarnings,
      httpErrors,
      screenshot: screenshotPath || null,
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
