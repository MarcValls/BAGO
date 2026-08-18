const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const binName = process.platform === 'win32' ? 'install-electron.cmd' : 'install-electron';
const repoRoot = path.join(__dirname, '..');
const localBin = path.join(__dirname, '..', 'node_modules', '.bin', binName);

if (!fs.existsSync(localBin)) {
  console.log('[postinstall] install-electron no disponible; se omite en este contexto.');
  process.exit(0);
}

const result = process.platform === 'win32'
  ? spawnSync('cmd.exe', ['/d', '/s', '/c', 'node_modules\\.bin\\install-electron.cmd'], {
      cwd: repoRoot,
      stdio: 'inherit',
      shell: false,
      windowsHide: true,
    })
  : spawnSync(localBin, [], {
      cwd: repoRoot,
      stdio: 'inherit',
      shell: false,
      windowsHide: true,
    });
if (result.error || result.status !== 0) {
  const code = typeof result.status === 'number' ? result.status : 1;
  console.error(`[postinstall] install-electron falló con código ${code}.`);
  process.exit(code);
}
