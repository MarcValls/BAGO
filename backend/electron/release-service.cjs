const { ReleaseJobManager } = require('./release-job-manager.cjs');

function createReleaseService(ctx) {
  const { BrowserWindow, os, path, getDependencyService } = ctx;
  let releaseJobs = null;

  function resolveUserRoot() {
    const override = String(process.env.BAGO_USER_ROOT || process.env.BAGO_ROOT || '').trim();
    if (override) return path.resolve(override);
    if (process.env.LOCALAPPDATA) return path.join(process.env.LOCALAPPDATA, 'BAGO');
    return path.join(os.homedir(), 'AppData', 'Local', 'BAGO');
  }

  function requireReleaseJobs() {
    if (!releaseJobs) throw new Error('Release Job Manager no inicializado');
    return releaseJobs;
  }

  function initReleaseJobs() {
    releaseJobs = new ReleaseJobManager({
      rootDir: path.join(resolveUserRoot(), 'manager', 'release-jobs')
    });
    releaseJobs.on('changed', job => {
      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) win.webContents.send('bago:release-job-changed', job);
      }
    });
  }

  function getState() {
    return {
      lifecycle_job: releaseJobs && releaseJobs.activeLifecycleJob || '',
      release_jobs: releaseJobs ? releaseJobs.listJobs().length : 0
    };
  }

  async function fetchReleases() {
    const dependency = getDependencyService();
    const ceiling = dependency.currentManagerVersion();
    const res = await fetch('https://api.github.com/repos/MarcValls/BAGO/releases?per_page=100', {
      headers: { Accept: 'application/vnd.github+json' }
    });
    if (!res.ok) throw new Error(`GitHub API HTTP ${res.status}`);
    const releases = await res.json();
    return (Array.isArray(releases) ? releases : [])
      .filter(r => !r.draft && !dependency.isFutureReleaseTag(r.tag_name, ceiling))
      .sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0))
      .map(r => ({
        tag_name: r.tag_name || '',
        html_url: r.html_url || '',
        prerelease: !!r.prerelease,
        published_at: r.published_at || '',
        name: r.name || r.tag_name || '',
        assets: Array.isArray(r.assets) ? r.assets.map(a => ({
          name: a.name || '',
          browser_download_url: a.browser_download_url || '',
          content_type: a.content_type || '',
          size: Number(a.size || 0),
          digest: a.digest || '',
          state: a.state || '',
          updated_at: a.updated_at || '',
          download_count: Number(a.download_count || 0)
        })) : []
      }));
  }

  return {
    requireReleaseJobs,
    initReleaseJobs,
    getState,
    fetchReleases
  };
}

module.exports = { createReleaseService };
