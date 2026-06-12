const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const source = path.join(root, 'assets', 'landing.css');
const target = path.join(root, 'landing', 'assets', 'landing.css');

fs.mkdirSync(path.dirname(target), { recursive: true });
fs.copyFileSync(source, target);
