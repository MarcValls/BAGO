/*
 * Real Electron accessibility smoke for the current Control Plane.
 * This is a deterministic structural audit, not a replacement for a full
 * WCAG/axe assessment: it checks names, labels, alternatives, duplicate IDs,
 * dialog names and visible focus targets across every destination.
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const DESTINATIONS = ['Inicio', 'Workspace', 'Contexto', 'Pipeline', 'Evidencia', 'Operaciones', 'Agentes', 'Intérprete', 'GitHub', 'Capacidades', 'Herramientas'];

function baseArgs(target) {
  const userData = String(process.env.BAGO_ELECTRON_USER_DATA_DIR || '').trim();
  return userData ? [`--user-data-dir=${userData}`, target] : [target];
}

async function auditPage(page, label) {
  const result = await page.evaluate((scope) => {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const style = getComputedStyle(element);
      return style.display !== 'none' && style.visibility !== 'hidden' && element.getClientRects().length > 0;
    };
    const text = (value) => String(value || '').replace(/\s+/g, ' ').trim();
    const accessibleName = (element) => {
      const aria = element.getAttribute('aria-label');
      if (aria) return text(aria);
      const labelledBy = element.getAttribute('aria-labelledby');
      if (labelledBy) return text(labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' '));
      const title = element.getAttribute('title');
      if (title) return text(title);
      return text(element.textContent);
    };
    const violations = [];
    for (const element of [...document.querySelectorAll('button, a')].filter(visible)) {
      if (!accessibleName(element)) violations.push(`${element.tagName.toLowerCase()} sin nombre accesible`);
    }
    for (const element of [...document.querySelectorAll('input, select, textarea')].filter(visible)) {
      const labelled = element.getAttribute('aria-label') || element.getAttribute('aria-labelledby');
      const id = element.getAttribute('id');
      const label = id && document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (!labelled && !label && !element.closest('label')) violations.push(`${element.tagName.toLowerCase()} sin label (${element.getAttribute('name') || id || 'anonimo'})`);
    }
    for (const element of [...document.querySelectorAll('img')].filter(visible)) {
      if (!element.hasAttribute('alt')) violations.push('img sin atributo alt');
    }
    const ids = [...document.querySelectorAll('[id]')].map((element) => element.id).filter(Boolean);
    for (const id of new Set(ids)) if (ids.filter((candidate) => candidate === id).length > 1) violations.push(`id duplicado: ${id}`);
    for (const dialog of [...document.querySelectorAll('[role="dialog"], dialog')].filter(visible)) {
      if (!accessibleName(dialog)) violations.push('dialog sin nombre accesible');
    }
    for (const element of [...document.querySelectorAll('[tabindex]')].filter(visible)) {
      if (Number(element.getAttribute('tabindex')) > 0) violations.push(`tabindex positivo: ${element.tagName.toLowerCase()}`);
    }
    return { scope, violations, visibleButtons: [...document.querySelectorAll('button')].filter(visible).length };
  }, label);
  return result;
}

async function main() {
  const smokeWorkspace = String(process.env.BAGO_A11Y_WORKSPACE || '').trim()
    || path.join(os.tmpdir(), `bago-a11y-${process.pid}`);
  fs.mkdirSync(path.join(smokeWorkspace, '.gabo'), { recursive: true });
  fs.writeFileSync(path.join(smokeWorkspace, '.gabo', 'workspace.json'), JSON.stringify({
    workspace_id: `ws-a11y-${process.pid}`, project_root: smokeWorkspace, workspace_scope_root: smokeWorkspace,
  }));
  const app = await electron.launch({
    args: baseArgs(ROOT),
    env: {
      ...process.env,
      BAGO_MANAGER_BASE_PATH: smokeWorkspace,
      BAGO_STATE_ROOT: path.join(smokeWorkspace, '.bago-test-state'),
      BAGO_MANAGER_AUTOMATION_TEST: '1',
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
  });
  const results = [];
  try {
    const page = await app.firstWindow();
    await page.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    await page.locator('.main-sidebar').waitFor({ state: 'visible', timeout: 120000 });
    const close = page.getByRole('button', { name: 'Cerrar recorrido', exact: true });
    if (await close.count() && await close.isVisible().catch(() => false)) await close.click();
    const sidebar = page.locator('.main-sidebar');
    for (const destination of DESTINATIONS) {
      const button = sidebar.getByRole('button', { name: new RegExp(`^${destination}\\b`) }).first();
      assert.strictEqual(await button.count(), 1, `destino ausente: ${destination}`);
      await button.click();
      await page.waitForTimeout(250);
      results.push(await auditPage(page, destination));
    }
    await sidebar.getByRole('button', { name: /^Inicio\b/ }).first().click();
    const model = page.getByRole('button', { name: 'Modelo de esta sesión', exact: true });
    if (await model.count()) { await model.click(); await page.waitForTimeout(150); results.push(await auditPage(page, 'Inicio/modelo')); await page.keyboard.press('Escape'); }
    await page.keyboard.press('Control+K');
    const command = page.getByRole('dialog', { name: 'Comandos rápidos' });
    if (await command.count()) { await command.waitFor({ state: 'visible' }); results.push(await auditPage(page, 'Inicio/comandos')); await page.keyboard.press('Escape'); }
    await page.keyboard.press('?');
    const help = page.getByRole('dialog', { name: /ayuda|atajos/i }).first();
    if (await help.count() && await help.isVisible().catch(() => false)) { results.push(await auditPage(page, 'Inicio/ayuda')); await page.keyboard.press('Escape'); }
    const violations = results.flatMap((entry) => entry.violations.map((violation) => `${entry.scope}: ${violation}`));
    assert.deepStrictEqual(violations, [], violations.join('\n'));
    console.log(JSON.stringify({ ok: true, scopes: results.map((entry) => entry.scope), violations, destinations: DESTINATIONS.length }));
  } finally {
    await app.close();
  }
}

main().catch((error) => { console.error(error && error.stack ? error.stack : error); process.exit(1); });
