const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const binName = process.platform === 'win32' ? 'install-electron.cmd' : 'install-electron';
const localBin = path.join(__dirname, '..', 'node_modules', '.bin', binName);

if (!fs.existsSync(localBin)) {
  console.log('[postinstall] install-electron no disponible; se omite en este contexto.');
  process.exit(0);
}

const result = spawnSync(localBin, [], { stdio: 'inherit', shell: false });
if (result.error || result.status !== 0) {
  const code = typeof result.status === 'number' ? result.status : 1;
  console.warn(`[postinstall] install-electron falló con código ${code}; se continúa para no bloquear install.`);
  process.exit(0);
}
