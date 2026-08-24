const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('../electron/release-job-manager.cjs');


async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bago-backup-resume-'));
  try {
    const manager = new ReleaseJobManager({ rootDir: path.join(root, 'jobs') });
    const target = path.join(root, 'runtime');
    const job = {
      id: 'fault-injection-job', target, backup_path: '', rollback_available: false,
      created_target: false, state: 'installing', updated_at: new Date().toISOString(),
      log_file: path.join(root, 'job.log.jsonl')
    };
    manager.jobs.set(job.id, job);

    fs.mkdirSync(target, { recursive: true });
    fs.writeFileSync(path.join(target, 'original.txt'), 'original');
    await manager._prepareAtomicBackup(job);
    const backup = `${target}.bago-rollback-${job.id}`;
    assert.strictEqual(fs.existsSync(path.join(backup, 'original.txt')), true);
    assert.strictEqual(fs.existsSync(target), false);

    // Crash boundary: the move happened, then the process lost in-memory
    // backup metadata. Resuming must rediscover, not delete, the backup.
    job.backup_path = '';
    job.rollback_available = false;
    await manager._prepareAtomicBackup(job);
    assert.strictEqual(fs.readFileSync(path.join(backup, 'original.txt'), 'utf8'), 'original');
    assert.strictEqual(job.backup_path, backup);
    assert.strictEqual(job.install_phase, 'backup_ready');

    // Crash after a replacement target appeared: preserve both original and
    // interrupted replacement before retrying installation.
    fs.mkdirSync(target, { recursive: true });
    fs.writeFileSync(path.join(target, 'partial.txt'), 'partial');
    await manager._prepareAtomicBackup(job);
    assert.strictEqual(fs.readFileSync(path.join(backup, 'original.txt'), 'utf8'), 'original');
    assert.strictEqual(fs.readFileSync(path.join(job.interrupted_target_path, 'partial.txt'), 'utf8'), 'partial');
    assert.strictEqual(fs.existsSync(target), false);

    console.log(JSON.stringify({ ok: true, backup_survives_resume: true, partial_preserved: true }));
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exit(1); });
