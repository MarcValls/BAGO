const assert = require('assert');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..');

async function main() {
  const app = await electron.launch({
    args: [ROOT],
    env: {
      ...process.env,
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
  });

  try {
    const window = await app.firstWindow();
    await window.waitForSelector('main.unified-app', { timeout: 120000 });
    await window.waitForSelector('aside.module-rail', { timeout: 120000 });
    await window.waitForSelector('header.manager-topbar', { timeout: 120000 });
    await window.waitForSelector('h1', { timeout: 120000 });

    const preloadReady = await window.evaluate(() => !!(window.bagoElectron && typeof window.bagoElectron.getManagerUrl === 'function'));
    assert.strictEqual(preloadReady, true, 'preload bridge missing');

    const topbarTitle = await window.locator('header.manager-topbar h1').innerText();
    const railLabel = await window.locator('aside.module-rail').getByText('Manager unificado').innerText();
    const shellVisible = await window.locator('main.unified-app').isVisible();
    const panelLocator = window.locator('aside.manager-panel');

    assert.ok(topbarTitle.length > 0, 'topbar title empty');
    assert.ok(railLabel.includes('Manager unificado'), railLabel);
    assert.strictEqual(shellVisible, true, 'manager shell not visible');

    const chatComposer = window.locator('textarea[aria-label="Mensaje al manager"]');
    const chatToggle = window.getByRole('button', { name: /^Chat$/ });
    const managerToggle = window.getByRole('button', { name: /^Men[uú]$/ });

    await managerToggle.click();
    await panelLocator.waitFor({ state: 'visible', timeout: 120000 });
    const panelLabel = await panelLocator.getAttribute('aria-label');
    assert.ok(panelLabel && panelLabel.length > 0, 'manager panel label empty');

    await chatToggle.click();
    await chatComposer.waitFor({ state: 'visible', timeout: 120000 });
    await chatComposer.fill('/status');
    await chatComposer.press('Enter');
    await window.locator('.chat-result strong').waitFor({ state: 'visible', timeout: 120000 });
    const chatResultText = await window.locator('.chat-result strong').innerText();
    assert.strictEqual(chatResultText.trim().toLowerCase(), 'done', 'chat result did not report done');

    await managerToggle.click();
    await panelLocator.waitFor({ state: 'visible', timeout: 120000 });
    assert.strictEqual(await panelLocator.isVisible(), true, 'manager panel did not become visible');

    await chatToggle.click();
    await panelLocator.waitFor({ state: 'hidden', timeout: 120000 });
    assert.strictEqual(await panelLocator.isVisible().catch(() => false), false, 'manager panel did not hide');

    await window.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
    const palette = window.getByRole('dialog', { name: 'Paleta de comandos' });
    await palette.waitFor({ state: 'visible', timeout: 120000 });
    await window.keyboard.press('Escape');
    await palette.waitFor({ state: 'hidden', timeout: 120000 });

    const reviewToggle = window.getByRole('button', { name: /^Review$/ });
    await reviewToggle.click();
    await window.locator('aside.module-rail').waitFor({ state: 'hidden', timeout: 120000 });
    await window.keyboard.press('Escape');
    await window.locator('aside.module-rail').waitFor({ state: 'visible', timeout: 120000 });
    const railClassAfterReview = await window.locator('aside.module-rail').getAttribute('class');
    assert.ok(!String(railClassAfterReview || '').includes('is-collapsed'), 'review mode did not restore rail state');

    console.log(JSON.stringify({
      ok: true,
      title: topbarTitle,
      preloadReady,
      panelLabel,
    }));
  } finally {
    await app.close();
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
