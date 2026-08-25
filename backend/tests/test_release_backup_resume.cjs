const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('../electron/release-job-manager.cjs');

function makeJob(root, id, target) {
  return {
    id, target, backup_path: '', rollback_available: false, created_target: false,
    state: 'installing', updated_at: new Date().toISOString(),
    log_file: path.join(root, `${id}.log.jsonl`),
  };
}

function persist(manager, job) {
  manager.jobs.set(job.id, job);
  manager._emit(job);
}

function restart(root, id) {
  const manager = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
  return { manager, job: manager._get(id) };
}

function crashAfterRename(matchSource, matchDestination) {
  const original = fs.renameSync;
  fs.renameSync = function injected(source, destination) {
    original.call(fs, source, destination);
    if (String(source).includes(matchSource) && String(destination).includes(matchDestination)) {
      throw new Error('injected crash after destructive boundary');
    }
  };
  return () => { fs.renameSync = original; };
}

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-backup-resume-'));
  try {
    const target1 = path.join(root, 'runtime-prepare');
    fs.mkdirSync(target1, { recursive: true });
    fs.writeFileSync(path.join(target1, 'original.txt'), 'original');
    let manager1 = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
    let job1 = makeJob(root, 'prepare-crash', target1);
    persist(manager1, job1);
    let restoreRename = crashAfterRename('runtime-prepare', '.bago-rollback-prepare-crash');
    await assert.rejects(() => manager1._prepareAtomicBackup(job1), /injected crash/);
    restoreRename();
    ({ manager: manager1, job: job1 } = restart(root, job1.id));
    await manager1._prepareAtomicBackup(job1);
    assert.strictEqual(fs.readFileSync(path.join(job1.backup_path, 'original.txt'), 'utf8'), 'original');

    const target2 = path.join(root, 'runtime-restore-target');
    fs.mkdirSync(target2, { recursive: true });
    fs.writeFileSync(path.join(target2, 'original.txt'), 'original');
    let manager2 = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
    let job2 = makeJob(root, 'restore-target-crash', target2);
    persist(manager2, job2);
    await manager2._prepareAtomicBackup(job2);
    fs.mkdirSync(target2, { recursive: true });
    fs.writeFileSync(path.join(target2, 'partial.txt'), 'partial');
    restoreRename = crashAfterRename('runtime-restore-target', '.bago-failed-restore-target-crash');
    await assert.rejects(() => manager2._restoreAtomicBackup(job2, true), /injected crash/);
    restoreRename();
    ({ manager: manager2, job: job2 } = restart(root, job2.id));
    await manager2._restoreAtomicBackup(job2, true);
    assert.strictEqual(fs.readFileSync(path.join(target2, 'original.txt'), 'utf8'), 'original');
    assert.strictEqual(fs.readFileSync(path.join(job2.replaced_path, 'partial.txt'), 'utf8'), 'partial');

    const target3 = path.join(root, 'runtime-restore-backup');
    fs.mkdirSync(target3, { recursive: true });
    fs.writeFileSync(path.join(target3, 'original.txt'), 'original');
    let manager3 = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
    let job3 = makeJob(root, 'restore-backup-crash', target3);
    persist(manager3, job3);
    await manager3._prepareAtomicBackup(job3);
    const backup3 = job3.backup_path;
    restoreRename = crashAfterRename('.bago-rollback-restore-backup-crash', 'runtime-restore-backup');
    await assert.rejects(() => manager3._restoreAtomicBackup(job3, true), /injected crash/);
    restoreRename();
    ({ manager: manager3, job: job3 } = restart(root, job3.id));
    await manager3._restoreAtomicBackup(job3, true);
    assert.strictEqual(fs.readFileSync(path.join(target3, 'original.txt'), 'utf8'), 'original');
    assert.strictEqual(fs.existsSync(backup3), false);
    assert.strictEqual(job3.restore_phase, 'restore_complete');

    console.log(JSON.stringify({ ok: true, persisted_restart: true, destructive_boundaries: 3 }));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exit(1); });
