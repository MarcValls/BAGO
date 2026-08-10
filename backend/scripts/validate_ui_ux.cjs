const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const url = process.env.BAGO_UI_URL || 'http://127.0.0.1:8080';
const root = path.resolve(__dirname, '..', '..');
const output = path.join(root, 'output', 'playwright');

async function clickSidebar(page, label) {
  const item = page.locator('.sidebar-item').filter({ has: page.locator('.sidebar-item-label', { hasText: new RegExp(`^${label}$`) }) }).first();
  await item.click();
  await item.waitFor({ state: 'visible' });
  assert.equal(await item.getAttribute('aria-current'), 'page', `No se activó la sección ${label}`);
  await page.waitForTimeout(350);
}

async function main() {
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 720 } });
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.addInitScript(() => {
    localStorage.setItem('bago.first-run.v1.completed', 'true');
    localStorage.setItem('bago.ui.state', JSON.stringify({ activeSection: 'home', appearanceTheme: 'dark', sidebarCollapsed: false }));
    sessionStorage.setItem('bago.start.chat-mode', 'open');
  });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded' });
    await page.locator('.app-root').waitFor({ timeout: 20_000 });
    await page.waitForTimeout(1_200);

    const navigation = (await page.locator('.sidebar-item').allInnerTexts()).map((value) => value.replace(/\s+/g, ' ').trim());
    assert.equal(navigation.length, 6, `Se esperaban 6 destinos: ${navigation.join(' | ')}`);
    assert.ok(!navigation.some((value) => value.includes('Grafo')), 'Grafo no debe ser un destino lateral');
    assert.equal(await page.locator('.first-run-backdrop').count(), 0, 'El recorrido inicial no debe bloquear un navegador ya preparado');
    assert.equal(await page.locator('.chat-message-body:visible').filter({ hasText: '[tool_calls]' }).count(), 0, 'Inicio expone tool_calls sin presentar');

    const homeOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(homeOverflow, false, 'Inicio desborda horizontalmente');
    await page.screenshot({ path: path.join(output, 'ux-home-dark.png'), fullPage: true });

    const authoritativeWorkspaceState = await page.evaluate(async () => {
      const response = await fetch('/api/v1/ui/bootstrap');
      const payload = await response.json();
      return String(payload?.status?.workspace_state?.workspace_state || payload?.status?.workspace_state?.state || '');
    });
    const authorityNotice = await page.locator('.workspace-authority-notice').count();
    if (authoritativeWorkspaceState === 'invalid') {
      assert.equal(authorityNotice, 1, 'La UI oculta un workspace que el backend declara inválido');
      assert.ok(!(await page.locator('.sidebar-status').innerText()).includes('Vinculado'), 'El lateral presenta como vinculado un workspace inválido');
    }
    if (authorityNotice) {
      const state = await page.locator('.sidebar-status').innerText();
      assert.match(state, /atención|preparar|inválido|bloque/i, `Estado incoherente con el aviso de workspace: ${state}`);
    }

    await clickSidebar(page, 'Contexto');
    await page.locator('.task-context-page').waitFor({ timeout: 15_000 });
    const contextText = await page.locator('.task-context-page').innerText();
    for (const label of ['Ahora', 'Tareas', 'Biblioteca', 'Más']) assert.ok(contextText.includes(label), `Falta ${label} en Contexto`);
    assert.ok(!contextText.includes('.gabo'), 'Contexto expone la ruta interna .gabo');
    assert.ok((contextText.match(/Recopilar del chat/g) || []).length <= 1, 'Contexto duplica la acción principal de recopilación');
    await page.screenshot({ path: path.join(output, 'ux-context-dark.png'), fullPage: true });

    await clickSidebar(page, 'Pipeline');
    await page.locator('.pipeline-view-tabs').waitFor({ timeout: 15_000 });
    await page.getByRole('button', { name: 'Ejecución', exact: true }).click();
    const workflowInput = page.getByLabel('Descripción del flujo de trabajo');
    await workflowInput.waitFor({ state: 'visible', timeout: 10_000 });
    const pipelineTaskMaxLength = Number(await workflowInput.getAttribute('maxlength'));
    assert.equal(pipelineTaskMaxLength, 24_000, 'El flujo de trabajo no admite 24.000 caracteres');
    assert.ok(Number(await workflowInput.getAttribute('rows')) >= 5, 'El flujo de trabajo sigue siendo demasiado pequeño');
    await page.screenshot({ path: path.join(output, 'ux-pipeline-execution-dark.png'), fullPage: true });
    await page.getByRole('button', { name: 'Flujo', exact: true }).click();
    await page.locator('.work-graph').waitFor({ timeout: 10_000 });
    const flowText = await page.locator('.work-graph').innerText();
    assert.ok(flowText.includes('De la mención a la ejecución'));
    assert.ok(flowText.includes('Iniciar') || flowText.includes('Sin tareas de contexto'));
    const graphBox = await page.locator('.work-graph').boundingBox();
    const surfaceBox = await page.locator('.surface-body').boundingBox();
    const flowCoverage = graphBox && surfaceBox ? graphBox.width / surfaceBox.width : 0;
    assert.ok(flowCoverage >= 0.85, `El Flujo solo ocupa ${Math.round(flowCoverage * 100)}% del ancho útil`);
    await page.screenshot({ path: path.join(output, 'ux-pipeline-flow-dark.png'), fullPage: true });

    await clickSidebar(page, 'Operación');
    await page.locator('.system-tabs').waitFor({ timeout: 10_000 });
    await page.screenshot({ path: path.join(output, 'ux-operation-dark.png'), fullPage: true });
    await page.getByRole('tab', { name: 'Capacidades', exact: true }).click();
    await page.locator('.system-capabilities-panel').waitFor({ timeout: 10_000 });

    await clickSidebar(page, 'Inicio');
    await page.locator('.chat-model-selector').click();
    assert.equal(await page.locator('.chat-model-search input').count(), 1, 'El selector de modelos no ofrece búsqueda');
    assert.ok((await page.locator('.chat-model-options').innerText()).includes('Automático'));
    await page.locator('.chat-model-picker').evaluate((element) => element.removeAttribute('open'));

    await page.locator('.header-theme-picker select').selectOption('light');
    await page.waitForTimeout(250);
    assert.ok(await page.locator('.app-root.theme-light').count(), 'El tema claro no se aplicó');
    const lightOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(lightOverflow, false, 'El tema claro desborda horizontalmente');
    await page.screenshot({ path: path.join(output, 'ux-home-light.png'), fullPage: true });

    assert.deepEqual(pageErrors, [], `Errores de página: ${pageErrors.join(' | ')}`);
    process.stdout.write(JSON.stringify({ ok: true, url, navigation, authoritativeWorkspaceState, authorityNotice: Boolean(authorityNotice), pipelineTaskMaxLength, flowCoverage, screenshots: fs.readdirSync(output).filter((name) => name.startsWith('ux-')) }, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
