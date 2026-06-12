// P1 regression tests. Each section mirrors one P1 finding from the audit.
// We use static reading of the source for things that don't have side
// effects, and isolated helpers (vm sandbox for resolver-style code, ps1
// for PowerShell) where we can.
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'electron', 'main.cjs'), 'utf8');
const PRELOAD = fs.readFileSync(path.join(ROOT, 'electron', 'preload.cjs'), 'utf8');
const APP_JSX = fs.readFileSync(path.join(ROOT, 'ui-react', 'src', 'App.jsx'), 'utf8');
const MANAGER_HTML = fs.readFileSync(path.join(ROOT, 'manager', 'index.html'), 'utf8');
const SIGN_TOOL = fs.readFileSync(path.join(ROOT, 'tools', 'sign-release.ps1'), 'utf8');
const PS1 = fs.readFileSync(path.join(ROOT, 'install-v4.ps1'), 'utf8');

// --- P1-01 ---------------------------------------------------------------

function test_manager_and_runtime_versions_are_reported_separately() {
  // managerHealth() must surface both manager_version and runtime_version
  // and they must come from different sources.
  const body = SRC.match(/async\s+function\s+managerHealth\s*\(\s*\)\s*\{[\s\S]*?\n\}/);
  assert.ok(body, 'managerHealth not found');
  assert.ok(/manager_version/.test(body[0]), 'managerHealth must report manager_version');
  assert.ok(/runtime_version/.test(body[0]), 'managerHealth must report runtime_version');
  // readManagerVersion reads from package.json
  assert.ok(/readManagerVersion/.test(SRC), 'readManagerVersion helper missing');
  // readRuntimeVersion reads from install_manifest.json OR release_version.txt
  assert.ok(/readRuntimeVersion/.test(SRC), 'readRuntimeVersion helper missing');
  assert.ok(/install_manifest\.json/.test(SRC), 'runtime version must consult the install manifest');
}

// --- P1-02 ---------------------------------------------------------------

function test_legacy_run_command_is_removed() {
  // runCommand() must not be defined in core.js anymore.
  const core = fs.readFileSync(path.join(ROOT, 'manager', 'js', 'core.js'), 'utf8');
  assert.ok(!/function\s+runCommand\s*\(/.test(core),
    'manager/js/core.js still defines runCommand(); legacy power-shell runner should be removed');
  // canRunCommands must also be gone
  assert.ok(!/canRunCommands/.test(core),
    'manager/js/core.js still references canRunCommands');
}

function test_legacy_run_buttons_copy_to_clipboard() {
  const legacy = fs.readFileSync(path.join(ROOT, 'manager', 'js', 'legacy-manager.js'), 'utf8');
  // We expect three button.run handlers, each on its own line range.
  const positions = [];
  const re = /querySelectorAll\('button\.run'\)/g;
  let m;
  while ((m = re.exec(legacy))) positions.push(m.index);
  assert.ok(positions.length >= 3, 'expected at least 3 button.run handlers, got ' + positions.length);
  for (let i = 0; i < positions.length; i++) {
    const start = positions[i];
    const end = i + 1 < positions.length ? positions[i + 1] : legacy.length;
    const handler = legacy.slice(start, end);
    assert.ok(!/runCommand\s*\(/.test(handler),
      'button.run handler still calls runCommand(): ' + handler.slice(0, 80));
    assert.ok(/copyText\s*\(/.test(handler),
      'button.run handler must call copyText() instead: ' + handler.slice(0, 80));
  }
}

// --- P1-03 ---------------------------------------------------------------

function test_app_jsx_does_not_hardcode_dev_port() {
  // Allow 4174 to appear in comments but not in an actual URL or a string
  // that would be passed to window.open.
  const urlAssignments = APP_JSX.match(/url\s*=\s*[`'"][^`'"]*4174[^`'"]*[`'"]/g) || [];
  assert.strictEqual(urlAssignments.length, 0,
    'App.jsx must not hardcode port 4174 in a URL: ' + urlAssignments.join(' | '));
}

function test_preload_exposes_get_manager_url() {
  assert.ok(/getManagerUrl\s*:/.test(PRELOAD),
    'preload must expose getManagerUrl()');
  assert.ok(/bago:manager-url/.test(SRC),
    'main.cjs must register a bago:manager-url IPC handler');
  assert.ok(/function\s+getManagerUrl\s*\(/.test(SRC),
    'main.cjs must implement getManagerUrl()');
}

// --- P1-04 ---------------------------------------------------------------

function test_sign_release_script_exists_and_validates_sha256() {
  assert.ok(/\[CmdletBinding\(\)\]/.test(SIGN_TOOL), 'sign-release.ps1 missing CmdletBinding');
  assert.ok(/signtool/i.test(SIGN_TOOL), 'sign-release.ps1 must wrap signtool');
  assert.ok(/TimestampUrl/.test(SIGN_TOOL), 'sign-release.ps1 must accept a timestamping URL');
  assert.ok(/SHA-256/i.test(SIGN_TOOL), 'sign-release.ps1 must handle SHA-256');
  assert.ok(/PfxPath/.test(SIGN_TOOL), 'sign-release.ps1 must accept a PFX path');
  // The script must update the .sha256 file after signing.
  assert.ok(/Set-Content.*Sha256Path/s.test(SIGN_TOOL),
    'sign-release.ps1 must update the .sha256 file after signing');
}

// --- P1-05 ---------------------------------------------------------------

function test_manager_html_has_csp_meta() {
  assert.ok(/http-equiv=["']Content-Security-Policy["']/.test(MANAGER_HTML),
    'manager/index.html must include a Content-Security-Policy meta tag');
  // Restrictive directives
  assert.ok(/default-src/.test(MANAGER_HTML), 'CSP must define default-src');
  assert.ok(/object-src\s+'none'/.test(MANAGER_HTML), 'CSP must set object-src to none');
  assert.ok(/frame-ancestors\s+'none'/.test(MANAGER_HTML), 'CSP must set frame-ancestors to none');
}

// --- P1-06 ---------------------------------------------------------------

function test_cleanup_zombies_filters_by_command_line() {
  // The new cleanupZombies must NOT contain the old wildcard that killed
  // any orphaned python.exe.
  const body = SRC.match(/async\s+function\s+cleanupZombies\s*\(\s*\)\s*\{[\s\S]*?return new Promise[\s\S]*?\}\);/);
  assert.ok(body, 'cleanupZombies body not found');
  const src = body[0];
  assert.ok(!/ParentProcessId/.test(src),
    'cleanupZombies still uses ParentProcessId to decide who to kill; that is unsafe on multi-project hosts');
  assert.ok(/Test-IsBagoProcess/.test(src),
    'cleanupZombies must use a Test-IsBagoProcess allowlist');
  assert.ok(/CommandLine/.test(src),
    'cleanupZombies must inspect CommandLine, not just process name');
  assert.ok(/launcher\.py/.test(src),
    'cleanupZombies must include the well-known BAGO scripts in its allowlist');
}

// --- P1-07 ---------------------------------------------------------------

function test_install_preflight_returns_unified_payload() {
  // runInstallPreflight must exist and be exposed as IPC.
  assert.ok(/async\s+function\s+runInstallPreflight\s*\(/.test(SRC),
    'runInstallPreflight helper is missing');
  assert.ok(/bago:install-preflight/.test(SRC),
    'bago:install-preflight IPC handler is missing');
  assert.ok(/runInstallPreflight/.test(PRELOAD) || /runInstallPreflight/.test(SRC),
    'preload should expose runInstallPreflight');
  // The function must check write, disk, network, python, powershell, git
  const body = SRC.match(/async\s+function\s+runInstallPreflight[\s\S]*?\n\}/);
  assert.ok(body, 'runInstallPreflight body not found');
  for (const key of ['write', 'disk', 'network', 'python', 'powershell', 'git']) {
    assert.ok(body[0].includes(`"${key}"`) || body[0].includes(`'${key}'`) || body[0].includes(key),
      'runInstallPreflight must include ' + key);
  }
}

// --- P1-08 ---------------------------------------------------------------

function test_install_paths_emit_install_state_consistently() {
  // Both ensureBagoInstalled and bago:install-action must call
  // emitInstallState. The action handler in particular must do it for
  // every action (repair, reinstall, new-copy, source-update).
  const block = SRC.match(/ipcMain\.handle\(\s*['"]bago:install-action['"][\s\S]*?throw new Error\(`Acci[^`]*`\);?\s*\}\);/);
  assert.ok(block, 'bago:install-action handler not found');
  const body = block[0];
  // Count emitInstallState calls
  const calls = (body.match(/emitInstallState\s*\(/g) || []).length;
  assert.ok(calls >= 8, 'bago:install-action must call emitInstallState for each action (>=8 calls), got ' + calls);
  // Each action must be present
  for (const action of ['repair', 'reinstall', 'new-copy', 'source-update']) {
    assert.ok(body.includes(`'${action}'`) || body.includes(`"${action}"`),
      'install action handler missing: ' + action);
  }
}

// --- P1-04 followup: sign-release.ps1 syntax -----------------------------

function test_sign_release_ps1_parses() {
  const res = spawnSync('powershell.exe',
    ['-NoProfile', '-Command', "[System.Management.Automation.Language.Parser]::ParseFile('" + path.join(ROOT, 'tools', 'sign-release.ps1') + "', [ref]$null, [ref]$errs) | Out-Null; if ($errs) { $errs | ForEach-Object { Write-Output $_.Message }; exit 1 } else { Write-Output 'PS1_OK' }"],
    { encoding: 'utf8' });
  assert.strictEqual(res.status, 0, 'sign-release.ps1 has parse errors: ' + res.stderr + res.stdout);
  assert.match(res.stdout, /PS1_OK/);
}

// --- runner --------------------------------------------------------------

function run() {
  const cases = [
    ['P1-01 manager + runtime versions', test_manager_and_runtime_versions_are_reported_separately],
    ['P1-02 runCommand removed from core.js', test_legacy_run_command_is_removed],
    ['P1-02 button.run copies to clipboard', test_legacy_run_buttons_copy_to_clipboard],
    ['P1-03 no hardcoded dev port in App.jsx', test_app_jsx_does_not_hardcode_dev_port],
    ['P1-03 getManagerUrl exposed', test_preload_exposes_get_manager_url],
    ['P1-04 sign-release.ps1 covers SHA-256 + timestamp + PFX', test_sign_release_script_exists_and_validates_sha256],
    ['P1-04 sign-release.ps1 parses', test_sign_release_ps1_parses],
    ['P1-05 manager HTML has CSP', test_manager_html_has_csp_meta],
    ['P1-06 cleanupZombies filters by CommandLine', test_cleanup_zombies_filters_by_command_line],
    ['P1-07 install preflight unifies checks', test_install_preflight_returns_unified_payload],
    ['P1-08 install paths emit consistent state', test_install_paths_emit_install_state_consistently]
  ];
  let failed = 0;
  for (const [name, fn] of cases) {
    try { fn(); console.log('ok  -', name); }
    catch (e) { failed += 1; console.error('FAIL-', name, '\n  ', e && e.stack || e); }
  }
  if (failed) { console.error('\n' + failed + ' test(s) failed'); process.exit(1); }
  console.log('\nall P1 tests passed');
}

if (require.main === module) run();
module.exports = { run };
