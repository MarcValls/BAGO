#!/usr/bin/env node
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('./release-job-manager.cjs');

const TERMINAL_OR_READY = new Set(['ready', 'completed', 'cancelled', 'failed', 'rolled-back']);

function usage() {
  console.log([
    'Uso:',
    '  bago release-job list [--json]',
    '  bago release-job fetch [--repo owner/name] [--tag TAG] [--output FILE] [--json]',
    '  bago release-job status <id> [--json]',
    '  bago release-job logs <id> [--limit N] [--json]',
    '  bago release-job preflight --release-json FILE --target DIR [--action update] [--json]',
    '  bago release-job prepare --release-json FILE --target DIR [--action update] [--mode Express] [--json]',
    '  bago release-job install <id> [--json]',
    '  bago release-job rollback <id> [--json]',
    '  bago release-job cancel <id> [--json]',
    '  bago release-job resume <id> [--json]'
  ].join('\n'));
}

function parse(argv) {
  const pos = [];
  const flags = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith('--')) {
      pos.push(item);
      continue;
    }
    const key = item.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    if (key === 'json' || key === 'requireSignature') {
      flags[key] = true;
      continue;
    }
    flags[key] = argv[i + 1] || '';
    i += 1;
  }
  return { pos, flags };
}

function manager() {
  return new ReleaseJobManager({
    rootDir: path.join(os.homedir(), '.bago', 'manager', 'release-jobs')
  });
}

function loadRelease(file) {
  if (!file) throw new Error('--release-json requerido');
  const raw = fs.readFileSync(path.resolve(file), 'utf8');
  return JSON.parse(raw);
}

function payload(flags) {
  return {
    release: loadRelease(flags.releaseJson),
    target: flags.target || '',
    action: flags.action || 'update',
    mode: flags.mode || 'Express',
    require_signature: !!flags.requireSignature
  };
}

function print(value, asJson = false) {
  if (asJson || typeof value !== 'string') {
    console.log(JSON.stringify(value, null, 2));
    return;
  }
  console.log(value);
}

async function fetchReleases(flags) {
  const repo = flags.repo || 'MarcValls/BAGO';
  const res = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=100`, {
    headers: { Accept: 'application/vnd.github+json' }
  });
  if (!res.ok) throw new Error(`GitHub releases HTTP ${res.status}`);
  const releases = await res.json();
  const rows = (Array.isArray(releases) ? releases : [])
    .filter(item => !item.draft)
    .sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0));
  const tag = String(flags.tag || '').trim();
  return tag ? rows.find(item => String(item.tag_name || '') === tag) || null : rows;
}

async function waitJob(jobs, id) {
  for (;;) {
    const job = jobs.getJob(id);
    if (TERMINAL_OR_READY.has(job.state)) return job;
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}

async function main(argv) {
  const { pos, flags } = parse(argv);
  const cmd = pos[0] || 'help';
  const jobs = manager();

  if (cmd === 'help' || cmd === '--help' || cmd === '-h') {
    usage();
    return 0;
  }
  if (cmd === 'list') {
    const rows = jobs.listJobs();
    if (flags.json) print(rows, true);
    else print(rows.map(job => `${job.id} ${job.state} ${job.release && job.release.tag_name || ''} -> ${job.target || ''}`).join('\n') || 'no release jobs');
    return 0;
  }
  if (cmd === 'fetch') {
    const releases = await fetchReleases(flags);
    if (!releases) throw new Error(`Release no encontrada: ${flags.tag}`);
    if (flags.output) {
      fs.writeFileSync(path.resolve(flags.output), JSON.stringify(releases, null, 2) + '\n', 'utf8');
      if (!flags.json) {
        print(`wrote ${path.resolve(flags.output)}`);
        return 0;
      }
    }
    print(releases, true);
    return 0;
  }
  if (cmd === 'status') {
    print(jobs.getJob(pos[1]), !!flags.json);
    return 0;
  }
  if (cmd === 'logs') {
    const rows = jobs.getLogs(pos[1], Number(flags.limit || 200));
    if (flags.json) print(rows, true);
    else print(rows.map(row => `${String(row.timestamp || '').slice(11, 19)} ${row.level || 'info'} ${row.message || ''}`).join('\n'));
    return 0;
  }
  if (cmd === 'preflight') {
    print(jobs.preflight(payload(flags)), !!flags.json);
    return 0;
  }
  if (cmd === 'prepare') {
    const started = jobs.startPrepare(payload(flags));
    print(await waitJob(jobs, started.id), !!flags.json);
    return 0;
  }
  if (cmd === 'resume') {
    const started = jobs.resume(pos[1]);
    print(await waitJob(jobs, started.id), !!flags.json);
    return 0;
  }
  if (cmd === 'cancel') {
    print(jobs.cancel(pos[1]), !!flags.json);
    return 0;
  }
  if (cmd === 'install') {
    print(await jobs.install(pos[1]), !!flags.json);
    return 0;
  }
  if (cmd === 'rollback') {
    print(await jobs.rollback(pos[1]), !!flags.json);
    return 0;
  }

  usage();
  return 1;
}

main(process.argv.slice(2)).then(
  code => process.exit(code),
  error => {
    console.error(error.message || error);
    process.exit(1);
  }
);
