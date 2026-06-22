const fs = require('node:fs/promises');
const path = require('node:path');
const AdmZip = require('adm-zip');
const { readReleaseVersion, readRepo } = require('./version_site.cjs');

async function removeDir(target) {
  await fs.rm(target, { recursive: true, force: true });
}

async function copyDir(src, dest) {
  await fs.mkdir(path.dirname(dest), { recursive: true });
  await fs.cp(src, dest, { recursive: true, force: true });
}

async function renderTemplate(templatePath, vars) {
  let text = await fs.readFile(templatePath, 'utf-8');
  for (const [key, value] of Object.entries(vars)) {
    const re = new RegExp(`\\$\\{${key}\\}`, 'g');
    text = text.replace(re, value);
  }
  // Also replace simple {{key}} style placeholders for safety.
  for (const [key, value] of Object.entries(vars)) {
    const re = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
    text = text.replace(re, value);
  }
  return text;
}

async function extractManagerZip(root, dest) {
  const zipPath = path.join(root, 'manager.zip');
  try {
    await fs.access(zipPath);
  } catch {
    return false;
  }
  const zip = new AdmZip(zipPath);
  const entries = zip.getEntries();
  for (const entry of entries) {
    if (entry.entryName.startsWith('manager/')) {
      const rel = entry.entryName.slice('manager/'.length);
      if (!rel || rel.endsWith('/')) continue;
      const target = path.join(dest, rel);
      await fs.mkdir(path.dirname(target), { recursive: true });
      await fs.writeFile(target, entry.getData());
    }
  }
  return true;
}

async function main() {
  const root = path.resolve(__dirname, '..');
  const dist = path.join(root, 'site-dist');

  const version = readReleaseVersion(root);
  const repo = readRepo(root);
  const releaseTag = `v${version}`;
  const managerName = `BAGO-Installation-Manager-${version}-win-x64.exe`;
  const bundleName = `bago-v${version}.zip`;

  const vars = {
    BAGO_VERSION: version,
    BAGO_RELEASE_TAG: releaseTag,
    BAGO_MANAGER_EXE: managerName,
    BAGO_BUNDLE_ZIP: bundleName,
    BAGO_REPO_OWNER: repo.owner,
    BAGO_REPO_NAME: repo.name,
    BAGO_REPO_BRANCH: repo.branch,
    BAGO_REPO_SLUG: repo.slug,
    BAGO_GITHUB_URL: repo.githubUrl,
    BAGO_RAW_URL: repo.rawUrl,
    BAGO_API_URL: repo.apiUrl,
    BAGO_RELEASES_URL: repo.releasesUrl,
    BAGO_INSTALL_REMOTE_URL: repo.installRemoteUrl,
    BAGO_MANAGER_DOWNLOAD_URL: `${repo.releasesUrl}/download/${releaseTag}/${managerName}`,
    BAGO_BUNDLE_DOWNLOAD_URL: `${repo.releasesUrl}/download/${releaseTag}/${bundleName}`,
    BAGO_BUNDLE_SHA256_URL: `${repo.releasesUrl}/download/${releaseTag}/${bundleName}.sha256`,
    BAGO_RELEASE_NOTES_URL: `${repo.releasesUrl}/tag/${releaseTag}`,
    BAGO_REPO_CONFIG_JSON: JSON.stringify({ owner: repo.owner, name: repo.name, branch: repo.branch, githubUrl: repo.githubUrl, apiUrl: repo.apiUrl, rawUrl: repo.rawUrl, releasesUrl: repo.releasesUrl }),
  };

  await removeDir(dist);
  await fs.mkdir(dist, { recursive: true });

  const indexHtml = await renderTemplate(path.join(root, 'index.html'), vars);
  await fs.writeFile(path.join(dist, 'index.html'), indexHtml, 'utf-8');

  // The legacy manager sub-site is distributed as manager.zip. Extract it
  // into site-dist/manager so /manager/ routes work on Vercel.
  const managerDest = path.join(dist, 'manager');
  const extracted = await extractManagerZip(root, managerDest);
  if (extracted) {
    const managerSrc = path.join(managerDest, 'index.html');
    try {
      const managerHtml = await renderTemplate(managerSrc, vars);
      await fs.writeFile(path.join(dist, 'manager.html'), managerHtml, 'utf-8');
    } catch (err) {
      console.warn('[build_vercel_site] manager/index.html not found in zip:', err.message);
    }
  } else {
    console.warn('[build_vercel_site] manager.zip not found; /manager will 404');
  }
}

main().catch((error) => {
  console.error('[build_vercel_site]', error);
  process.exit(1);
});
