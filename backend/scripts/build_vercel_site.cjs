const fs = require('node:fs/promises');
const path = require('node:path');

async function removeDir(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function copyFile(src, dest) {
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.copyFile(src, dest);
}

async function copyDir(src, dest) {
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.cp(src, dest, { recursive: true, force: true });
}

async function main() {
  const root = path.resolve(__dirname, '..');
  const dist = path.join(root, 'site-dist');

  await removeDir(dist);
  await fs.mkdir(dist, { recursive: true });

  await copyFile(path.join(root, 'index.html'), path.join(dist, 'index.html'));
  await copyFile(path.join(root, 'manager', 'index.html'), path.join(dist, 'manager.html'));
  await copyDir(path.join(root, 'manager'), path.join(dist, 'manager'));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
