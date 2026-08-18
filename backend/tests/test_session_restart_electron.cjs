const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..');

async function openApp(smokeWorkspace) {
  return electron.launch({
    args: [ROOT],
    env: {
      ...process.env,
      BAGO_MANAGER_BASE_PATH: smokeWorkspace,
      BAGO_STATE_ROOT: path.join(smokeWorkspace, '.bago-test-state'),
      BAGO_MANAGER_AUTOMATION_TEST: '1',
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
  });
}

async function readyWindow(app) {
  const window = await app.firstWindow();
  await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
  const close = window.getByRole('button', { name: 'Cerrar recorrido', exact: true });
  if (await close.isVisible().catch(() => false)) await close.click();
  const entryState = await window.waitForFunction(() => {
    const model = document.querySelector('#bago-chat-model');
    if (model instanceof HTMLSelectElement && model.offsetParent) return 'chat';
    const start = document.querySelector('.start-chat-actions .primary-button');
    if (start instanceof HTMLButtonElement && start.offsetParent) return 'welcome';
    return '';
  }, null, { timeout: 120000 }).then((handle) => handle.jsonValue());
  if (entryState === 'welcome') await window.locator('.start-chat-actions .primary-button').click();
  await window.locator('#bago-chat-model').waitFor({ state: 'visible', timeout: 120000 });
  if (await close.waitFor({ state: 'visible', timeout: 5000 }).then(() => true).catch(() => false)) await close.click();
  return window;
}

async function main() {
  const smokeWorkspace = path.join(os.tmpdir(), `bago-session-restart-${process.pid}`);
  fs.mkdirSync(path.join(smokeWorkspace, '.gabo'), { recursive: true });
  fs.writeFileSync(path.join(smokeWorkspace, '.gabo', 'workspace.json'), JSON.stringify({
    workspace_id: `ws-restart-${process.pid}`,
    project_root: smokeWorkspace,
    workspace_scope_root: smokeWorkspace,
  }, null, 2));
  fs.cpSync(path.join(ROOT, '.bago', 'context'), path.join(smokeWorkspace, '.bago', 'context'), { recursive: true });

  let firstApp = await openApp(smokeWorkspace);
  let restoredSessionId = '';
  let restoredConversationId = '';
  let fallbackSessionId = '';
  try {
    const firstWindow = await readyWindow(firstApp);
    const sessionSelect = firstWindow.getByLabel('Sesión activa');
    const initialSessionId = await sessionSelect.inputValue();
    fallbackSessionId = initialSessionId;
    await firstWindow.getByRole('button', { name: 'Nueva sesión', exact: true }).click();
    await firstWindow.waitForFunction((initialId) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && !select.disabled && Boolean(select.value) && select.value !== initialId;
    }, initialSessionId, { timeout: 60000 });
    restoredSessionId = await sessionSelect.inputValue();
    const close = firstWindow.getByRole('button', { name: 'Cerrar recorrido', exact: true });
    if (await close.isVisible().catch(() => false)) await close.click();

    const conversationSelect = firstWindow.getByLabel('Conversación activa');
    await firstWindow.getByRole('button', { name: 'Nueva conversación', exact: true }).click();
    await firstWindow.waitForFunction(() => {
      const select = document.querySelector('#bago-conversation-select');
      return select instanceof HTMLSelectElement && !select.disabled && select.value.startsWith('chat-');
    }, null, { timeout: 60000 });
    restoredConversationId = await conversationSelect.inputValue();

    await firstWindow.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    let sessionDialog = firstWindow.getByRole('dialog', { name: 'Gestionar sesión' });
    await sessionDialog.getByLabel('Nombre de la sesión').fill('Sesión archivada reiniciable');
    await sessionDialog.getByRole('button', { name: 'Guardar nombre', exact: true }).click();
    await sessionDialog.waitFor({ state: 'detached', timeout: 30000 });
    await firstWindow.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    sessionDialog = firstWindow.getByRole('dialog', { name: 'Gestionar sesión' });
    await sessionDialog.getByRole('button', { name: 'Archivar', exact: true }).click();
    const archiveConfirmation = firstWindow.getByRole('dialog', { name: 'Archivar sesión' });
    await archiveConfirmation.getByRole('button', { name: 'Archivar sesión', exact: true }).click();
    await firstWindow.waitForFunction((archivedSessionId) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && Boolean(select.value) && select.value !== archivedSessionId && !select.disabled;
    }, restoredSessionId, { timeout: 60000 });
    fallbackSessionId = await sessionSelect.inputValue();
  } finally {
    await firstApp.close();
  }

  const secondApp = await openApp(smokeWorkspace);
  try {
    const secondWindow = await readyWindow(secondApp);
    const sessionSelect = secondWindow.getByLabel('Sesión activa');
    const conversationSelect = secondWindow.getByLabel('Conversación activa');
    await sessionSelect.waitFor({ state: 'visible', timeout: 60000 });
    await conversationSelect.waitFor({ state: 'visible', timeout: 60000 });
    assert.strictEqual(await sessionSelect.inputValue(), fallbackSessionId);
    await secondWindow.getByRole('button', { name: 'Gestionar sesión', exact: true }).click();
    const sessionDialog = secondWindow.getByRole('dialog', { name: 'Gestionar sesión' });
    await sessionDialog.getByLabel('Buscar sesiones archivadas').fill('reiniciable');
    await sessionDialog.getByRole('button', { name: 'Restaurar Sesión archivada reiniciable', exact: true }).click();
    await sessionDialog.waitFor({ state: 'detached', timeout: 30000 });
    await secondWindow.waitForFunction((expected) => {
      const select = document.querySelector('#bago-session-select');
      return select instanceof HTMLSelectElement && select.value === expected.sessionId && !select.disabled;
    }, { sessionId: restoredSessionId }, { timeout: 60000 });
    assert.strictEqual(await conversationSelect.inputValue(), restoredConversationId);
    const screenshotPath = String(process.env.BAGO_ELECTRON_RESTART_SCREENSHOT || '').trim();
    if (screenshotPath) {
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
      await secondWindow.screenshot({ path: screenshotPath });
    }
    console.log(JSON.stringify({
      ok: true,
      restoredSessionId,
      restoredConversationId,
      screenshot: screenshotPath || null,
    }));
  } finally {
    await secondApp.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
