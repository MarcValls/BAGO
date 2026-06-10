// P0-02 regression tests for the installer's UAC / fallback decision.
// We extract the decision block from install-v4.ps1 and run it under
// PowerShell with a controlled Test-IsAdministrator override.
'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const PS1 = fs.readFileSync(path.join(__dirname, '..', 'install-v4.ps1'), 'utf8');

function extractBlock(startAnchor, endAnchor) {
  const i = PS1.indexOf(startAnchor);
  if (i < 0) throw new Error('start anchor not found: ' + startAnchor);
  const j = PS1.indexOf(endAnchor, i + 1);
  if (j < 0) throw new Error('end anchor not found: ' + endAnchor);
  return PS1.slice(i, j);
}

function runPwsh(script) {
  const res = spawnSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script], {
    encoding: 'utf8'
  });
  return { status: res.status, stdout: res.stdout || '', stderr: res.stderr || '' };
}

function psEscape(s) { return "'" + String(s).replace(/'/g, "''") + "'"; }

// P0-02: when not admin and InstallDir is under Program Files, the script
// must NOT keep the Program Files path; it must fall back to LOCALAPPDATA
// (we cannot auto-elevate in a non-interactive test, so we only check the
// fallback branch's effect on $InstallDir).
function test_fallback_when_not_admin_and_program_files() {
  const block = extractBlock('if ($Profile -eq "stable"', 'function Test-ReleaseExcluded');
  const script = `
    $ErrorActionPreference = 'Stop'
    $InstallDir = 'C:\\Program Files\\BAGO'
    $Profile = 'stable'
    # Override Test-IsAdministrator to always return $false in this test
    function Test-IsAdministrator { return $false }
    ${block}
    Write-Output ("install_dir=" + $InstallDir)
  `;
  const r = runPwsh(script);
  assert.strictEqual(r.status, 0, r.stderr);
  // default InstallDir is C:\Program Files\BAGO. With non-admin override
  // the block should switch the install dir to %LOCALAPPDATA%\BAGO.
  assert.match(r.stdout, /install_dir=.*BAGO/);
  assert.ok(!/^install_dir=C:\\Program Files\\BAGO$/m.test(r.stdout),
    'install dir should not stay in Program Files when not admin: ' + r.stdout);
  assert.match(r.stdout, /AppData[\\\/]Local[\\\/]BAGO/);
}

// P0-02: when admin, the script keeps the original (Program Files) path.
function test_keep_program_files_when_admin() {
  const block = extractBlock('if ($Profile -eq "stable"', 'function Test-ReleaseExcluded');
  const script = `
    $ErrorActionPreference = 'Stop'
    function Test-IsAdministrator { return $true }
    $InstallDir = 'C:\\Program Files\\BAGO'
    ${block}
    Write-Output ("install_dir=" + $InstallDir)
  `;
  const r = runPwsh(script);
  assert.strictEqual(r.status, 0, r.stderr);
  assert.match(r.stdout, /install_dir=C:\\Program Files\\BAGO/);
}

// P0-02: when InstallDir is already in a user-writable location, the block
// must not touch it, even when the user is not admin.
function test_user_writable_path_untouched() {
  const block = extractBlock('if ($Profile -eq "stable"', 'function Test-ReleaseExcluded');
  const script = `
    $ErrorActionPreference = 'Stop'
    function Test-IsAdministrator { return $false }
    $InstallDir = 'C:\\Users\\someone\\AppData\\Local\\BAGO-dev'
    ${block}
    Write-Output ("install_dir=" + $InstallDir)
  `;
  const r = runPwsh(script);
  assert.strictEqual(r.status, 0, r.stderr);
  assert.match(r.stdout, /install_dir=C:\\Users\\someone\\AppData\\Local\\BAGO-dev/);
}

// P0-02: des/ign profiles install into user-writable paths and must not
// trigger the elevation/fallback block.
function test_des_and_ign_profiles_skip_elevation_block() {
  const block = extractBlock('if ($Profile -eq "stable"', 'function Test-ReleaseExcluded');
  const forDes = `
    $ErrorActionPreference = 'Stop'
    function Test-IsAdministrator { return $false }
    $InstallDir = 'C:\\Program Files\\BAGO'
    $Profile = 'des'
    ${block}
    Write-Output ("install_dir=" + $InstallDir)
  `;
  const forIgn = `
    $ErrorActionPreference = 'Stop'
    function Test-IsAdministrator { return $false }
    $InstallDir = 'C:\\Program Files\\BAGO'
    $Profile = 'ign'
    ${block}
    Write-Output ("install_dir=" + $InstallDir)
  `;
  for (const script of [forDes, forIgn]) {
    const r = runPwsh(script);
    assert.strictEqual(r.status, 0, r.stderr);
    assert.match(r.stdout, /install_dir=C:\\Program Files\\BAGO/,
      'des/ign profiles must NOT be auto-redirected to %LOCALAPPDATA%');
  }
}

// P0-02 regression: Quote-PwshArg must round-trip values that contain
// spaces and double quotes, and pass through simple values untouched.
function test_quote_pwsh_arg() {
  const script = `
    ${extractBlock('function Quote-PwshArg', 'function Test-IsAdministrator')}
    Write-Output ("plain=" + (Quote-PwshArg 'hello'))
    Write-Output ("empty=" + (Quote-PwshArg ''))
    Write-Output ("spaces=" + (Quote-PwshArg 'a b c'))
    Write-Output ("quote=" + (Quote-PwshArg 'a"b'))
    Write-Output ("dollar=" + (Quote-PwshArg 'a$env:PATH'))
  `;
  const r = runPwsh(script);
  assert.strictEqual(r.status, 0, r.stderr);
  assert.match(r.stdout, /plain=hello/);
  assert.match(r.stdout, /empty=""/);
  assert.match(r.stdout, /spaces="a b c"/);
  assert.match(r.stdout, /quote="a""b"/);
  assert.match(r.stdout, /dollar="a\$env:PATH"/);
}

function run() {
  if (process.platform !== 'win32' && !process.env.BAGO_TEST_FORCE_PWSH) {
    console.log('skip - P0-02 ps1 tests (non-Windows host)');
    return;
  }
  const cases = [
    ['P0-02 fallback to LOCALAPPDATA when not admin', test_fallback_when_not_admin_and_program_files],
    ['P0-02 keep Program Files when admin', test_keep_program_files_when_admin],
    ['P0-02 user-writable path untouched', test_user_writable_path_untouched],
    ['P0-02 des/ign profiles skip elevation block', test_des_and_ign_profiles_skip_elevation_block],
    ['P0-02 Quote-PwshArg round-trips risky values', test_quote_pwsh_arg]
  ];
  let failed = 0;
  for (const [name, fn] of cases) {
    try { fn(); console.log('ok  -', name); }
    catch (e) { failed += 1; console.error('FAIL-', name, '\n  ', e && e.stack || e); }
  }
  if (failed) { console.error('\n' + failed + ' test(s) failed'); process.exit(1); }
  console.log('\nall P0-02 UAC tests passed');
}

if (require.main === module) run();
module.exports = { run };
