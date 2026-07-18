const fs = require('fs');
const path = require('path');

function createAuditService(ctx) {
  const {
    ROOT_DIR,
    resolveInstalledRuntimeRoot,
    getDependencyService,
    getReleaseService
  } = ctx;

  function readText(filePath) {
    try {
      return fs.readFileSync(filePath, 'utf8');
    } catch {
      return '';
    }
  }

  function readJson(filePath) {
    try {
      return JSON.parse(readText(filePath) || '{}');
    } catch {
      return null;
    }
  }

  function normalizeVersion(value) {
    return String(value || '').trim().replace(/^v/i, '');
  }

  function extractVersionFromText(text) {
    const match = String(text || '').match(/(?:^|\n)\s*(?:version|version:)\s*([0-9A-Za-z.+-]+)/i);
    return match ? normalizeVersion(match[1]) : '';
  }

  function duplicateValues(values) {
    const seen = new Map();
    for (const value of values) {
      const key = String(value || '').trim();
      if (!key) continue;
      seen.set(key, (seen.get(key) || 0) + 1);
    }
    return Array.from(seen.entries()).filter(([, count]) => count > 1).map(([value, count]) => ({ value, count }));
  }

  function countMatches(text, pattern) {
    const source = String(text || '');
    const re = new RegExp(pattern, 'gi');
    const matches = source.match(re);
    return matches ? matches.length : 0;
  }

  function makeFinding(severity, scope, code, title, detail, file) {
    return {
      severity,
      scope,
      code,
      title,
      detail,
      file: file || ''
    };
  }

  function projectAudit() {
    const pkg = readJson(path.join(ROOT_DIR, 'package.json')) || {};
    const packageVersion = normalizeVersion(pkg.version || '');
    const releaseVersion = normalizeVersion(readText(path.join(ROOT_DIR, 'release_version.txt')));
    const latestYml = readText(path.join(ROOT_DIR, 'dist', 'latest.yml'));
    const readme = readText(path.join(ROOT_DIR, 'README.md'));
    const manual = readText(path.join(ROOT_DIR, 'MANUAL.md'));
    const html = readText(path.join(ROOT_DIR, 'manager', 'index.html'));
    const findings = [];

    if (packageVersion && releaseVersion && packageVersion !== releaseVersion) {
      findings.push(makeFinding('high', 'project', 'VERSION_DRIFT', 'package.json y release_version.txt no coinciden', `${packageVersion} vs ${releaseVersion}`, 'package.json'));
    }

    const distVersion = extractVersionFromText(latestYml);
    if (packageVersion && distVersion && packageVersion !== distVersion) {
      findings.push(makeFinding('high', 'project', 'DIST_DRIFT', 'dist/latest.yml desalineado', `${packageVersion} vs ${distVersion}`, 'dist/latest.yml'));
    }

    const releaseNotes = path.join(ROOT_DIR, 'docs', `RELEASE_NOTES_${packageVersion}.md`);
    if (packageVersion && !fs.existsSync(releaseNotes)) {
      findings.push(makeFinding('medium', 'project', 'MISSING_RELEASE_NOTES', 'Faltan notas de release canónicas', `No existe ${path.relative(ROOT_DIR, releaseNotes)}`, releaseNotes));
    }

    const duplicateIds = duplicateValues(Array.from(html.matchAll(/id="([^"]+)"/g)).map(match => match[1]));
    if (duplicateIds.length) {
      findings.push(makeFinding('high', 'project', 'DUPLICATE_IDS', 'IDs duplicados en manager/index.html', duplicateIds.map(item => `${item.value}×${item.count}`).join(', '), 'manager/index.html'));
    }

    const pmDetailCount = countMatches(html, 'id="pm-detail"');
    if (pmDetailCount > 1) {
      findings.push(makeFinding('high', 'project', 'DUPLICATE_DETAIL', 'pm-detail duplicado', `id="pm-detail" aparece ${pmDetailCount} veces`, 'manager/index.html'));
    }

    if (packageVersion && !readme.includes(packageVersion)) {
      findings.push(makeFinding('low', 'project', 'README_VERSION', 'README no menciona la versión actual', `No aparece ${packageVersion}`, 'README.md'));
    }

    if (packageVersion && !manual.includes(packageVersion)) {
      findings.push(makeFinding('low', 'project', 'MANUAL_VERSION', 'MANUAL no menciona la versión actual', `No aparece ${packageVersion}`, 'MANUAL.md'));
    }

    return {
      scope: 'project',
      checked_at: new Date().toISOString(),
      root: ROOT_DIR,
      version: packageVersion || 'unknown',
      summary: {
        findings: findings.length,
        high: findings.filter(item => item.severity === 'high').length,
        medium: findings.filter(item => item.severity === 'medium').length,
        low: findings.filter(item => item.severity === 'low').length
      },
      sources: {
        package_json: !!pkg,
        release_version: releaseVersion || '',
        dist_latest: distVersion || '',
        readme_has_version: packageVersion ? readme.includes(packageVersion) : false,
        manual_has_version: packageVersion ? manual.includes(packageVersion) : false
      },
      findings
    };
  }

  function bagoAudit() {
    const dependency = getDependencyService();
    const release = getReleaseService();
    const runtimeRoot = resolveInstalledRuntimeRoot();
    const pkg = readJson(path.join(ROOT_DIR, 'package.json')) || {};
    const packageVersion = normalizeVersion(pkg.version || '');
    const findings = [];
    const managerHealth = dependency.managerHealth();
    const releaseState = release.getState();
    const runtimeVersion = runtimeRoot ? normalizeVersion(readText(path.join(runtimeRoot, 'release_version.txt'))) : '';
    const hasManifest = !!(runtimeRoot && fs.existsSync(path.join(runtimeRoot, 'install_manifest.json')));
    const hasLauncher = !!(runtimeRoot && fs.existsSync(path.join(runtimeRoot, 'bago_core', 'launcher.py')));

    if (!runtimeRoot) {
      findings.push(makeFinding('high', 'bago', 'NO_RUNTIME', 'No hay runtime instalado', 'No se detectó una instalación viva de BAGO', 'runtime'));
    } else {
      if (!hasLauncher) {
        findings.push(makeFinding('high', 'bago', 'MISSING_LAUNCHER', 'Falta launcher en el runtime', 'No existe bago_core/launcher.py en la instalación detectada', runtimeRoot));
      }
      if (!hasManifest) {
        findings.push(makeFinding('medium', 'bago', 'NO_MANIFEST', 'La instalación no tiene manifiesto', 'install_manifest.json no existe en la instalación detectada', runtimeRoot));
      }
      if (packageVersion && runtimeVersion && packageVersion !== runtimeVersion) {
        findings.push(makeFinding('medium', 'bago', 'VERSION_DRIFT', 'Runtime desalineado con el repo', `${packageVersion} vs ${runtimeVersion}`, runtimeRoot));
      }
    }

    const startup = managerHealth && managerHealth.startup || {};
    const missingCore = Array.isArray(startup.missing_core) ? startup.missing_core : [];
    if (missingCore.length) {
      findings.push(makeFinding('medium', 'bago', 'MISSING_DEPENDENCIES', 'Dependencias faltantes', missingCore.map(item => item.id).join(', '), 'manager health'));
    }

    if (managerHealth && managerHealth.mutation) {
      findings.push(makeFinding('low', 'bago', 'ACTIVE_MUTATION', 'Mutación activa', managerHealth.mutation.action || 'node mutation', 'runtime'));
    }
    if (releaseState && Number(releaseState.release_jobs || 0) > 0) {
      findings.push(makeFinding('low', 'bago', 'RELEASE_JOBS', 'Trabajos persistentes', `${releaseState.release_jobs} trabajos`, 'release jobs'));
    }

    return {
      scope: 'bago',
      checked_at: new Date().toISOString(),
      runtime_root: runtimeRoot || '',
      repo_root: ROOT_DIR,
      version: packageVersion || 'unknown',
      summary: {
        findings: findings.length,
        high: findings.filter(item => item.severity === 'high').length,
        medium: findings.filter(item => item.severity === 'medium').length,
        low: findings.filter(item => item.severity === 'low').length
      },
      health: managerHealth,
      release_state: releaseState,
      sources: {
        runtime_version: runtimeVersion || '',
        manifest: hasManifest,
        launcher: hasLauncher
      },
      findings
    };
  }

  function eventLedger(limit = 60) {
    const managerHealth = getDependencyService().managerHealth();
    const releaseState = getReleaseService().getState();
    const events = [];
    const append = (scope, action, detail, source, severity = 'info') => {
      events.push({
        timestamp: new Date().toISOString(),
        scope,
        action,
        detail,
        source,
        severity
      });
    };

    if (managerHealth && Array.isArray(managerHealth.checks)) {
      managerHealth.checks.forEach(check => {
        append('bago', check.name || 'check', check.detail || '', 'manager health', check.ok ? 'info' : 'warn');
      });
    }
    if (managerHealth && managerHealth.mutation) {
      append('bago', 'mutacion', managerHealth.mutation.action || '', 'runtime', 'warn');
    }
    if (releaseState && releaseState.release_jobs) {
      append('bago', 'release_jobs', String(releaseState.release_jobs), 'release service', 'info');
    }

    return {
      scope: 'ledger',
      checked_at: new Date().toISOString(),
      entries: events.slice(0, Number(limit || 60)),
      summary: {
        entries: events.length
      }
    };
  }

  return {
    projectAudit,
    bagoAudit,
    eventLedger
  };
}

module.exports = {
  createAuditService
};
