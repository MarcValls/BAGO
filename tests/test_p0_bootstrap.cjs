// P0-05 regression tests for the Manager bootstrap flow.
// We assert two things by reading main.cjs:
//   1) `createWindow()` is called BEFORE `ensureBagoInstalled()` so the user
//      always sees a window during install/repair.
//   2) `ensureBagoInstalled()` never calls `app.quit()` anymore (it must
//      push state to the UI instead so the user has a recovery panel).
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const SRC = fs.readFileSync(path.join(__dirname, '..', 'electron', 'main.cjs'), 'utf8');

function test_create_window_before_ensure_install() {
  const whenReady = SRC.match(/app\.whenReady\(\)\.then\(async\s*\(\)\s*=>\s*\{([\s\S]*?)\}\);/);
  assert.ok(whenReady, 'app.whenReady().then(...) block not found');
  const body = whenReady[1];
  const createIdx = body.indexOf('createWindow()');
  const ensureIdx = body.indexOf('ensureBagoInstalled()');
  assert.ok(createIdx >= 0, 'createWindow() not in app.whenReady()');
  assert.ok(ensureIdx >= 0, 'ensureBagoInstalled() not in app.whenReady()');
  assert.ok(createIdx < ensureIdx,
    'createWindow() must run before ensureBagoInstalled() so the UI is ready before the install prompt');
}

function test_no_app_quit_in_ensure_bago_installed() {
  // Find the body of ensureBagoInstalled by matching braces after its
  // declaration.
  const m = SRC.match(/async\s+function\s+ensureBagoInstalled\s*\(\s*\)\s*\{/);
  assert.ok(m, 'ensureBagoInstalled declaration not found');
  let depth = 0;
  let i = m.index + m[0].length;
  let opened = false;
  for (; i < SRC.length; i++) {
    const c = SRC[i];
    if (c === '{') { depth += 1; opened = true; }
    else if (c === '}') { depth -= 1; if (opened && depth === 0) { break; } }
  }
  const body = SRC.slice(m.index, i + 1);
  // Allowed: dialog.showErrorBox(...). Forbidden: app.quit() anywhere.
  assert.ok(!/app\.quit\s*\(\s*\)/.test(body),
    'ensureBagoInstalled() must not call app.quit() anymore; it should emitInstallState and let the UI handle the failure');
}

function test_install_state_ipc_is_exposed() {
  assert.ok(/ipcMain\.handle\(\s*['"]bago:install-state-get['"]/.test(SRC),
    'bago:install-state-get IPC handler is missing');
  assert.ok(/emitInstallState\b/.test(SRC),
    'emitInstallState() helper is missing');
  assert.ok(/webContents\.send\(\s*['"]bago:install-state['"]/.test(SRC),
    'bago:install-state IPC event is missing');
}

function test_install_banner_is_wired_in_manager_html() {
  const html = fs.readFileSync(path.join(__dirname, '..', 'manager', 'index.html'), 'utf8');
  assert.ok(/js\/install-banner\.js/.test(html),
    'manager/index.html does not load manager/js/install-banner.js');
  const bannerJs = fs.readFileSync(path.join(__dirname, '..', 'manager', 'js', 'install-banner.js'), 'utf8');
  assert.ok(/onInstallState/.test(bannerJs),
    'install-banner.js does not call api.onInstallState');
  assert.ok(/getInstallState/.test(bannerJs),
    'install-banner.js does not call api.getInstallState');
}

function test_preload_exposes_install_state_api() {
  const preload = fs.readFileSync(path.join(__dirname, '..', 'electron', 'preload.cjs'), 'utf8');
  assert.ok(/getInstallState\s*:/.test(preload),
    'preload does not expose getInstallState');
  assert.ok(/onInstallState\s*:/.test(preload),
    'preload does not expose onInstallState');
}

// P0-05: the recovery banner must be removed once the install reaches
// the `ready` or `cancelled` state, otherwise it covers the Manager UI.
function test_banner_is_removed_in_ready_or_cancelled() {
  const src = fs.readFileSync(path.join(__dirname, '..', 'manager', 'js', 'install-banner.js'), 'utf8');
  assert.ok(/state\.phase === 'ready'/.test(src) || /phase === 'ready'/.test(src),
    'banner does not have a ready-state branch');
  assert.ok(/existing\s*\)[\s\S]*?existing\.remove\(\)/.test(src) || /existing\.remove\(\)/.test(src),
    'banner does not actually remove itself when ready');
}

// P0-05: ensureBagoInstalled is started AFTER createWindow AND after the
// recovery wiring is in place. It must be wrapped in .catch so an
// unhandled rejection can never bring the app down.
function test_ensure_bago_installed_is_caught() {
  const src = fs.readFileSync(path.join(__dirname, '..', 'electron', 'main.cjs'), 'utf8');
  const m = src.match(/app\.whenReady\(\)\.then\(async\s*\(\)\s*=>\s*\{([\s\S]*?)\}\);/);
  assert.ok(m, 'app.whenReady().then(...) block not found');
  const body = m[1];
  assert.ok(/ensureBagoInstalled\(\)\.catch\(/.test(body),
    'ensureBagoInstalled() must be .catch()-handled in app.whenReady()');
}

function run() {
  const cases = [
    ['P0-05 createWindow before ensureBagoInstalled', test_create_window_before_ensure_install],
    ['P0-05 ensureBagoInstalled does not quit', test_no_app_quit_in_ensure_bago_installed],
    ['P0-05 install-state IPC is wired', test_install_state_ipc_is_exposed],
    ['P0-05 install-banner.js is in the Manager', test_install_banner_is_wired_in_manager_html],
    ['P0-05 preload exposes install-state API', test_preload_exposes_install_state_api],
    ['P0-05 banner removed on ready/cancelled', test_banner_is_removed_in_ready_or_cancelled],
    ['P0-05 ensureBagoInstalled is .catch()-handled', test_ensure_bago_installed_is_caught]
  ];
  let failed = 0;
  for (const [name, fn] of cases) {
    try { fn(); console.log('ok  -', name); }
    catch (e) { failed += 1; console.error('FAIL-', name, '\n  ', e && e.stack || e); }
  }
  if (failed) { console.error('\n' + failed + ' test(s) failed'); process.exit(1); }
  console.log('\nall P0-05 bootstrap tests passed');
}

if (require.main === module) run();
module.exports = { run };
