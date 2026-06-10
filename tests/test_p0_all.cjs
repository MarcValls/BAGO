// Aggregate runner for all P0 regression tests. This file is just a
// convenience for CI; individual test files remain runnable on their own.
'use strict';

const TESTS = [
  { name: 'P0-01 install resolver', file: './test_p0_install_resolver.cjs' },
  { name: 'P0-02 UAC / fallback', file: './test_p0_uac.cjs' },
  { name: 'P0-03/P0-04 PS1', file: './test_p0_install_ps1.cjs' },
  { name: 'P0-05 bootstrap', file: './test_p0_bootstrap.cjs' },
  { name: 'P1', file: './test_p1.cjs' }
];

let failed = 0;
for (const t of TESTS) {
  console.log('\n=== ' + t.name + ' ===');
  const r = require(t.file);
  try {
    r.run();
  } catch (e) {
    failed += 1;
    console.error('runner failed for', t.name, e);
  }
}
if (failed) {
  console.error('\n' + failed + ' test file(s) had failures');
  process.exit(1);
} else {
  console.log('\nALL P0 TESTS PASSED');
}
