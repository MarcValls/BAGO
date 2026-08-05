const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { _electron: electron } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const VIEWER = path.join(ROOT, 'electron-viewer');
const ELECTRON = path.join(ROOT, 'node_modules', 'electron', 'dist', 'electron.exe');
const PACKAGE_ZIP = process.env.BAGO_CAPABILITY_PACKAGE_ZIP
  || path.join(ROOT, 'output', 'playwright', 'local.text-stats-1.0.0.zip');
const SCREENSHOT = process.env.BAGO_CAPABILITY_SCREENSHOT
  || path.join(ROOT, 'output', 'playwright', 'electron-capability-package.png');

async function dismissTour(window) {
  const close = window.getByRole('button', { name: 'Cerrar recorrido', exact: true });
  if (await close.isVisible().catch(() => false)) await close.click();
}

async function main() {
  assert.ok(fs.existsSync(ELECTRON), `Electron no encontrado: ${ELECTRON}`);
  assert.ok(fs.existsSync(PACKAGE_ZIP), `ZIP no encontrado: ${PACKAGE_ZIP}`);

  const app = await electron.launch({ executablePath: ELECTRON, args: ['.'], cwd: VIEWER });
  const consoleErrors = [];
  try {
    const window = await app.firstWindow();
    window.on('console', (message) => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    window.on('pageerror', (error) => consoleErrors.push(error.message));
    await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    await window.evaluate(() => {
      localStorage.setItem('bago.first-run.v1.completed', 'true');
      sessionStorage.setItem('bago.start.chat-mode', 'open');
    });
    await window.reload({ waitUntil: 'domcontentloaded' });
    await window.locator('.app-root').waitFor({ state: 'visible', timeout: 120000 });
    await dismissTour(window);

    const viewerFlag = await window.evaluate(() => Boolean(window.bagoElectron?.isViewer));
    assert.equal(viewerFlag, true, 'La prueba no está ejecutándose en el visor Electron');

    await window.locator('.sidebar-item').filter({ hasText: 'Grafo' }).click();
    await window.getByRole('button', { name: 'Capacidades', exact: true }).click();
    await window.locator('.capability-anatomy').waitFor({ state: 'visible', timeout: 30000 });
    await window.getByRole('button', { name: 'Externas', exact: true }).click();
    await window.locator('.capability-packages').waitFor({ state: 'visible', timeout: 30000 });

    const importButton = window.getByRole('button', { name: 'Importar', exact: true });
    assert.equal(await importButton.isDisabled(), true, 'Importar debe exigir archivo y confianza');
    await window.getByLabel('Paquete ZIP').setInputFiles(PACKAGE_ZIP);
    await window.getByRole('checkbox', { name: 'Confío en este código local' }).check();
    assert.equal(await importButton.isEnabled(), true);
    await importButton.click();

    await window.getByText('Estadísticas de texto', { exact: true }).last().waitFor({ state: 'visible', timeout: 30000 });
    const detail = window.locator('.capability-package-detail');
    const activation = detail.getByRole('button', { name: 'Activar', exact: true });
    if (await activation.isVisible().catch(() => false)) await activation.click();
    await detail.getByRole('button', { name: 'Desactivar', exact: true }).waitFor({ state: 'visible', timeout: 30000 });

    const executeButton = detail.getByRole('button', { name: 'Ejecutar con receipt', exact: true });
    assert.equal(await executeButton.isDisabled(), true, 'Ejecutar debe exigir confirmación');
    await detail.getByRole('checkbox', { name: 'Convertir a minúsculas' }).check();
    await detail.getByRole('button', { name: 'Guardar configuración', exact: true }).click();
    await detail.getByLabel('Texto').fill('Hola MUNDO desde Electron');
    await detail.getByRole('checkbox', { name: /Confirmo esta ejecución/ }).check();
    await executeButton.click();

    const receipt = detail.locator('.capability-receipt[data-status="succeeded"]');
    await receipt.waitFor({ state: 'visible', timeout: 130000 });
    assert.ok((await receipt.innerText()).includes('hola mundo desde electron'));

    await detail.getByRole('button', { name: 'Desactivar', exact: true }).click();
    await detail.getByRole('button', { name: 'Activar', exact: true }).waitFor({ state: 'visible', timeout: 30000 });
    await detail.getByRole('button', { name: 'Activar', exact: true }).click();
    await detail.getByRole('button', { name: 'Desactivar', exact: true }).waitFor({ state: 'visible', timeout: 30000 });

    const fit = await window.evaluate(() => {
      const root = document.documentElement;
      const panel = document.querySelector('.capability-packages')?.getBoundingClientRect();
      const footer = document.querySelector('.capability-anatomy > footer')?.getBoundingClientRect();
      return {
        width: window.innerWidth,
        height: window.innerHeight,
        overflowX: root.scrollWidth > root.clientWidth,
        overflowY: root.scrollHeight > root.clientHeight,
        panelInside: Boolean(panel && panel.left >= 0 && panel.right <= window.innerWidth && panel.top >= 0 && panel.bottom <= window.innerHeight),
        footerInside: Boolean(footer && footer.bottom <= window.innerHeight),
      };
    });
    assert.equal(fit.overflowX, false);
    assert.equal(fit.overflowY, false);
    assert.equal(fit.panelInside, true);
    assert.equal(fit.footerInside, true);

    fs.mkdirSync(path.dirname(SCREENSHOT), { recursive: true });
    await window.screenshot({ path: SCREENSHOT });
    const relevantErrors = consoleErrors.filter((entry) => !entry.includes('favicon'));
    assert.deepEqual(relevantErrors, []);
    console.log(JSON.stringify({ ok: true, viewerFlag, fit, screenshot: SCREENSHOT }));
  } finally {
    await app.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
