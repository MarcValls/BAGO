const fs = require('node:fs');
const path = require('node:path');

function readReleaseVersion(root) {
  const candidates = [
    path.join(root, 'release_version.txt'),
    path.join(root, '.bago', 'release_version.txt'),
  ];
  for (const candidate of candidates) {
    try {
      const value = fs.readFileSync(candidate, 'utf-8').trim();
      if (value) return value.replace(/^v/i, '');
    } catch {
      // ignore
    }
  }
  const versionsPath = path.join(root, 'versions.json');
  try {
    const data = JSON.parse(fs.readFileSync(versionsPath, 'utf-8'));
    if (data.current) return String(data.current).replace(/^v/i, '');
  } catch {
    // ignore
  }
  return 'current';
}

function readRepo(root) {
  const repoPath = path.join(root, 'repo.json');
  try {
    const data = JSON.parse(fs.readFileSync(repoPath, 'utf-8'));
    const owner = String(data.owner || 'MarcValls').trim();
    const name = String(data.name || 'BAGO').trim();
    const branch = String(data.branch || 'main').trim();
    const slug = `${owner}/${name}`;
    return {
      owner,
      name,
      branch,
      slug,
      githubUrl: `https://github.com/${slug}`,
      rawUrl: `https://raw.githubusercontent.com/${slug}/${branch}`,
      apiUrl: `https://api.github.com/repos/${slug}`,
      releasesUrl: `https://github.com/${slug}/releases`,
      installRemoteUrl: `https://raw.githubusercontent.com/${slug}/${branch}/install-remote.ps1`,
    };
  } catch {
    // Canonical fallback so the site still renders if repo.json is missing.
    return {
      owner: 'MarcValls',
      name: 'BAGO',
      branch: 'main',
      slug: 'MarcValls/BAGO',
      githubUrl: 'https://github.com/MarcValls/BAGO',
      rawUrl: 'https://raw.githubusercontent.com/MarcValls/BAGO/main',
      apiUrl: 'https://api.github.com/repos/MarcValls/BAGO',
      releasesUrl: 'https://github.com/MarcValls/BAGO/releases',
      installRemoteUrl: 'https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1',
    };
  }
}

module.exports = { readReleaseVersion, readRepo };
