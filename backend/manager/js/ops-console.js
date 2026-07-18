let pmCurrentRoutePlan = null;

function pmCurrentSession() {
  return typeof pmSession !== 'undefined' ? pmSession : null;
}

function pmLatestStableRelease() {
  return (typeof pmStableReleases === 'function' ? pmStableReleases() : releaseItems.filter(rel => !rel.prerelease))[0] || latestRelease || null;
}

function pmLatestManagerAsset() {
  const rel = pmLatestStableRelease();
  const assets = Array.isArray(rel && rel.assets) ? rel.assets : [];
  return assets.find(asset => /BAGO-Installation-Manager.*\.exe$/i.test(asset.name || '')) || null;
}

function pmSelectedInstallPath() {
  const selected = typeof pmFindInstallation === 'function' ? pmFindInstallation(pmSelectedInstallation) : null;
  const detected = typeof existingInstallations === 'function' ? existingInstallations() : [];
  return (selected && selected.path) || (detected[0] && detected[0].path) || (pmManagerHealth && pmManagerHealth.runtime_root) || 'C:\\Program Files\\BAGO';
}

function pmControlButton(label, action, tone = '', extra = '') {
  return '<button class="pm-btn ' + escapeHtml(tone) + '" data-control-action="' + escapeHtml(action) + '" ' + extra + '>' + escapeHtml(label) + '</button>';
}

function pmControlCard(title, subtitle, status, body, actions, tone = '') {
  return '<article class="pm-control-card ' + escapeHtml(tone) + '">'
    + '<div class="pm-control-head"><div><h2>' + escapeHtml(title) + '</h2><p>' + escapeHtml(subtitle) + '</p></div>' + status + '</div>'
    + '<div class="pm-control-body">' + body + '</div>'
    + '<div class="pm-control-actions">' + actions + '</div>'
    + '</article>';
}

function pmControlKv(label, value, cls = '') {
  return '<div class="pm-control-kv"><span>' + escapeHtml(label) + '</span><strong class="' + escapeHtml(cls) + '">' + escapeHtml(value || '-') + '</strong></div>';
}

function pmRenderControl() {
  const box = document.getElementById('pm-control-grid');
  if (!box) return;
  const api = electronApi();
  const detected = typeof existingInstallations === 'function' ? existingInstallations() : [];
  const health = pmManagerHealth || {};
  const startup = health.startup || {};
  const requiredMissing = Array.isArray(startup.required_missing) ? startup.required_missing : [];
  const recommendedMissing = Array.isArray(startup.recommended_missing) ? startup.recommended_missing : [];
  const missing = requiredMissing.concat(recommendedMissing);
  const stable = pmLatestStableRelease();
  const managerAsset = pmLatestManagerAsset();
  const target = pmSelectedInstallPath();
  const activeJobs = releaseJobs.filter(job => !['ready', 'completed', 'cancelled', 'failed', 'rolled-back'].includes(job.state));
  const terminalJobs = releaseJobs.filter(job => ['ready', 'completed', 'cancelled', 'failed', 'rolled-back'].includes(job.state));
  const session = pmCurrentSession();
  const providers = (session && Array.isArray(session.providers) && session.providers.length ? session.providers : pmLocalProviderCatalog());
  const providerRows = providers.map(provider => {
    const spec = pmProviderSpec(provider.name);
    const actions = [];
    if (pmProviderAuthModes(provider.name).includes('api')) actions.push(pmControlButton('API', 'provider-api', 'primary', 'data-provider="' + escapeHtml(provider.name) + '"'));
    if (pmProviderAuthModes(provider.name).includes('login')) actions.push(pmControlButton('Login', 'provider-login', '', 'data-provider="' + escapeHtml(provider.name) + '"'));
    if (pmProviderAuthModes(provider.name).includes('install')) actions.push(pmControlButton('Instalar', 'provider-install', '', 'data-provider="' + escapeHtml(provider.name) + '"'));
    return '<div class="pm-provider-line"><div><strong>' + escapeHtml(spec.label || provider.name) + '</strong><span>' + escapeHtml((provider.models || []).slice(0, 2).join(' / ') || 'sin modelos') + '</span></div>'
      + pmBadge(provider.configured ? 'listo' : 'pendiente', provider.configured ? 'ok' : 'warn')
      + '<div class="pm-provider-actions-inline">' + actions.join('') + '</div></div>';
  }).join('');

  box.innerHTML = [
    pmControlCard(
      'Runtime',
      'Instalacion activa y reparacion',
      pmBadge(health.runtime_root ? 'detectado' : 'sin runtime', health.runtime_root ? 'ok' : 'bad'),
      pmControlKv('Runtime', health.runtime_root || target)
        + pmControlKv('Manager', health.manager_version || managerVersion || '-')
        + pmControlKv('Runtime version', health.runtime_version || 'sin leer'),
      pmControlButton('Abrir chat', 'open-web-chat', 'primary')
        + pmControlButton('CLI', 'open-cli-chat')
        + pmControlButton('Reparar', 'repair')
        + pmControlButton('Reinstalar', 'reinstall')
        + pmControlButton('Nueva copia', 'new-copy'),
      health.runtime_root ? '' : 'warn'
    ),
    pmControlCard(
      'Dependencias',
      'Arranque y providers',
      pmBadge(missing.length ? missing.length + ' faltan' : 'ok', missing.length ? 'warn' : 'ok'),
      missing.length
        ? missing.map(dep => pmControlKv(dep.label || dep.id, dep.detail || 'pendiente', dep.required ? 'bad' : 'warn')).join('')
        : pmControlKv('Estado', startup.prompt || 'Arranque listo', 'ok'),
      pmControlButton('Instalar faltantes', 'install-missing-deps', missing.length ? 'primary' : '', missing.length ? '' : 'disabled')
        + pmControlButton('Ver salud', 'open-health'),
      missing.length ? 'warn' : ''
    ),
    pmControlCard(
      'Providers',
      'API key o login segun proveedor',
      pmBadge(providers.filter(item => item.configured).length + '/' + providers.length, 'info'),
      '<div class="pm-provider-stack">' + providerRows + '</div>',
      pmControlButton('Configurar sesion', 'open-sessions', 'primary')
        + pmControlButton('Ruta provider', 'route-provider'),
      ''
    ),
    pmControlCard(
      'Releases',
      'Manager y runtime compatibles',
      pmBadge(stable && stable.tag_name || 'sin release', stable ? 'ok' : 'warn'),
      pmControlKv('Ultima permitida', stable && stable.tag_name || '-')
        + pmControlKv('Manager asset', managerAsset && managerAsset.name || 'no publicado')
        + pmControlKv('Jobs', releaseJobs.length + ' persistidos'),
      pmControlButton('Descargar manager', 'download-manager', 'primary', managerAsset ? '' : 'disabled')
        + pmControlButton('Preparar update', 'prepare-update')
        + pmControlButton('Ver releases', 'open-releases'),
      ''
    ),
    pmControlCard(
      'Instalaciones',
      'Roles, update y eliminacion',
      pmBadge(detected.length + ' detectadas', detected.length ? 'ok' : 'warn'),
      pmControlKv('Seleccionada', target)
        + pmControlKv('Supervisores vivos', detected.filter(item => item.supervisor_alive).length + '/' + detected.length)
        + pmControlKv('Roles', (installSelection && installSelection.roles ? Object.keys(installSelection.roles).length : 0) + ' asignados'),
      pmControlButton('Ver instalaciones', 'open-installations', 'primary')
        + pmControlButton('Archivar seleccionada', 'delete-install', 'danger')
        + pmControlButton('Ruta release', 'route-release'),
      ''
    ),
    pmControlCard(
      'Trabajos',
      'Descarga, verificacion, instalacion y rollback',
      pmBadge(activeJobs.length ? activeJobs.length + ' activos' : 'sin activos', activeJobs.length ? 'warn' : 'ok'),
      pmControlKv('Persistidos', String(releaseJobs.length))
        + pmControlKv('Terminales', String(terminalJobs.length))
        + pmControlKv('Con rollback', String(releaseJobs.filter(job => job.rollback_available).length)),
      pmControlButton('Ver trabajos', 'open-jobs', 'primary')
        + pmControlButton('Archivar terminales', 'delete-terminal-jobs', 'danger', terminalJobs.length ? '' : 'disabled')
        + pmControlButton('Ruta completa', 'route-project'),
      ''
    )
  ].join('');

  box.querySelectorAll('[data-control-action]').forEach(btn => {
    btn.addEventListener('click', () => pmHandleControlAction(btn));
  });
}

async function pmHandleControlAction(btn) {
  const action = btn.getAttribute('data-control-action') || '';
  const api = electronApi();
  const target = pmSelectedInstallPath();
  try {
    if (action === 'open-web-chat') return openWebChat();
    if (action === 'open-cli-chat') return openCliChat();
    if (action === 'open-health') return pmSwitchView('health');
    if (action === 'open-sessions') return pmSwitchView('sessions');
    if (action === 'open-releases') return pmSwitchView('releases');
    if (action === 'open-jobs') return pmSwitchView('jobs');
    if (action === 'open-installations') return pmSwitchView('installations');
    if (action === 'route-project') return pmBuildRoute('project');
    if (action === 'route-release') return pmBuildRoute('release');
    if (action === 'route-provider') return pmBuildRoute('provider');
    if (action === 'download-manager') {
      const asset = pmLatestManagerAsset();
      if (!asset || !asset.browser_download_url) return showToast('Manager asset no disponible', false);
      window.open(asset.browser_download_url, '_blank', 'noopener');
      return;
    }
    if (action === 'install-missing-deps') {
      const missing = ((pmManagerHealth && pmManagerHealth.startup && pmManagerHealth.startup.missing_core) || []).filter(item => item.install_command);
      if (!missing.length) return showToast('No hay dependencias instalables pendientes', true);
      if (api && typeof api.dependencyAction !== 'function') {
        throw new Error('dependencyAction no disponible en Electron');
      }
      if (!api) {
        await copyText(missing.map(item => item.install_command).join('; '));
        return;
      }
      const result = await api.dependencyAction({ action: 'install-all', targets: missing.map(item => item.id) });
      if (result && result.command) {
        await copyText(result.command);
        return showToast('Comando copiado; ejecútalo manualmente si procede', true);
      }
      return showToast('Instaladores iniciados en segundo plano', true);
    }
    if (action === 'repair' || action === 'reinstall') {
      if (api && typeof api.installAction !== 'function') {
        throw new Error('installAction no disponible en Electron');
      }
      if (!api) {
        await copyText(action === 'repair' ? 'bago repair' : 'bago update');
        return;
      }
      await api.installAction({ action, targetDir: target });
      await refreshAll([]);
      await pmLoadHealth();
      return showToast(action === 'repair' ? 'Reparacion terminada' : 'Reinstalacion terminada', true);
    }
    if (action === 'new-copy') {
      const next = window.prompt('Ruta para nueva copia BAGO:', target.replace(/\\BAGO$/i, '\\BAGO-copy'));
      if (!next) return;
      if (api && typeof api.installAction !== 'function') {
        throw new Error('installAction no disponible en Electron');
      }
      if (!api) {
        await copyText(installCommand(latestRelease && latestRelease.tag_name || '', next));
        return;
      }
      await api.installAction({ action: 'new-copy', targetDir: next });
      await refreshAll([next]);
      return showToast('Nueva copia creada', true);
    }
    if (action === 'prepare-update') {
      const rel = pmLatestStableRelease();
      if (!rel) return showToast('No hay release compatible cargada', false);
      return pmPrepareRelease(rel, target, 'update');
    }
    if (action === 'delete-install') return pmUninstallInstallation(target);
    if (action === 'delete-terminal-jobs') return pmDeleteTerminalJobs();
    if (action === 'provider-api') {
      if (!api) return showToast('Las API keys se guardan desde Electron', false);
      if (typeof api.dependencyAction !== 'function') throw new Error('dependencyAction no disponible en Electron');
      return pmProviderAction('api', btn.getAttribute('data-provider') || '');
    }
    if (action === 'provider-login') {
      const provider = btn.getAttribute('data-provider') || '';
      if (api && typeof api.dependencyAction !== 'function') {
        throw new Error('dependencyAction no disponible en Electron');
      }
      if (!api) {
        const cmd = pmProviderLoginCommand(provider);
        if (cmd) await copyText(cmd);
        return;
      }
      return pmProviderAction('login', provider);
    }
    if (action === 'provider-install') {
      const provider = btn.getAttribute('data-provider') || '';
      const dep = pmDependencySpec(pmProviderSpec(provider).installTarget || '');
      if (api && typeof api.dependencyAction !== 'function') {
        throw new Error('dependencyAction no disponible en Electron');
      }
      if (!api) {
        if (dep && dep.installCommand) await copyText(dep.installCommand);
        return;
      }
      return pmProviderAction('install', provider);
    }
  } catch (error) {
    showToast(error.message || 'Accion fallida', false);
  }
}

async function pmDeleteTerminalJobs() {
  const api = electronApi();
  const jobs = releaseJobs.filter(job => ['ready', 'completed', 'cancelled', 'failed', 'rolled-back'].includes(job.state));
  if (!jobs.length) return showToast('No hay trabajos terminales', true);
  if (!api || !api.deleteReleaseJob) return showToast('deleteReleaseJob no disponible', false);
  if (!window.confirm('Archivar ' + jobs.length + ' trabajo(s) terminal(es)?')) return;
  for (const job of jobs) await api.deleteReleaseJob(job.id);
  await pmLoadJobs();
  showToast('Trabajos archivados', true);
}

function pmRouteNode(layer, title, detail, tone = '') {
  return '<div class="pm-route-node ' + escapeHtml(tone) + '"><span>' + escapeHtml(layer) + '</span><strong>' + escapeHtml(title) + '</strong><small>' + escapeHtml(detail) + '</small></div>';
}

function pmRoutePlan(kind) {
  const session = pmCurrentSession() || {};
  const provider = session.provider || 'ollama-local';
  const model = session.model || 'llama3.2:3b';
  const agent = session.active_agent || 'default';
  const target = pmSelectedInstallPath();
  const release = pmLatestStableRelease();
  const templates = {
    project: {
      title: 'Pipeline para analizar y trabajar un proyecto',
      command: 'bago project analyze',
      output: 'Mapa del proyecto, bugs probables, mejoras y comandos de build/test.',
      nodes: [
        ['Entrada', 'Directorio de trabajo', 'cwd o ruta indicada por el usuario', 'input'],
        ['Intencion', 'project.analyze', 'clasifica stack, estructura y riesgos', 'intent'],
        ['Modelo', provider + ' / ' + model, 'resuelve lenguaje natural y prioridades', 'model'],
        ['Agente', agent, 'orquesta lectura, diagnostico y acciones', 'agent'],
        ['Tools/Skills', 'project_memory + dep_audit', 'lee archivos, dependencias y señales', 'tool'],
        ['Comando', 'bago project analyze', 'produce evidencia operativa', 'command'],
        ['Salida', 'Plan accionable', 'bugs, mejoras y compilacion sugerida', 'output']
      ]
    },
    release: {
      title: 'Pipeline para actualizar o instalar release',
      command: 'release job -> prepare -> install',
      output: 'Job verificable con SHA256, staging, backup atomico y rollback.',
      nodes: [
        ['Entrada', release && release.tag_name || 'release compatible', target, 'input'],
        ['Preflight', 'ReleaseJobManager', 'contrato ZIP + SHA256 + destino', 'intent'],
        ['Modelo', 'sin LLM obligatorio', 'decision determinista del manager', 'model'],
        ['Agente', 'release-service', 'filtra futuras y prepara job', 'agent'],
        ['Scripts', 'install-v4.ps1', 'instala desde staging verificado', 'tool'],
        ['Comando', 'prepare/update/install', 'ciclo de vida controlado', 'command'],
        ['Salida', 'Runtime actualizado', 'logs, rollback y evidencia', 'output']
      ]
    },
    provider: {
      title: 'Pipeline para registrar provider',
      command: 'dependencyAction: api/login/install',
      output: 'Provider listo para sesion con API key, login o dependencia local.',
      nodes: [
        ['Entrada', 'Provider', provider, 'input'],
        ['Decision', 'authModes', 'API key, login o instalacion', 'intent'],
        ['Modelo', provider + ' / ' + model, 'catalogo de modelos disponibles', 'model'],
        ['Agente', 'session-manager', 'aplica provider/modelo/bridges', 'agent'],
        ['Tools', 'credential_manager', 'guarda credenciales por provider', 'tool'],
        ['Comando', 'dependencyAction', 'set-credential, login o winget', 'command'],
        ['Salida', 'Sesion configurada', 'provider usable por chat y jobs', 'output']
      ]
    },
    audit: {
      title: 'Pipeline para auditar ruta y evidencia',
      command: 'bago node validate / evidence',
      output: 'Ledger de cambios, validacion y estado de connectors.',
      nodes: [
        ['Entrada', 'Estado actual', 'instalaciones, pieces, connectors', 'input'],
        ['Intencion', 'audit.validate', 'comprueba drift y contratos', 'intent'],
        ['Modelo', 'opcional', 'solo resume si se solicita', 'model'],
        ['Agente', 'node-control', 'valida registry y matriz', 'agent'],
        ['Tools', 'evidence ledger', 'recoge cambios y resultados', 'tool'],
        ['Comando', 'bago node validate', 'devuelve ok/fallos', 'command'],
        ['Salida', 'Evidencia', 'exportable y trazable', 'output']
      ]
    }
  };
  return templates[kind] || templates.project;
}

function pmBuildRoute(kind) {
  const select = document.getElementById('pm-route-template');
  if (select) select.value = kind;
  pmCurrentRoutePlan = pmRoutePlan(kind);
  pmSwitchView('route');
  pmRenderRoute();
}

function pmRenderRoute() {
  const board = document.getElementById('pm-route-board');
  const output = document.getElementById('pm-route-output');
  const caption = document.getElementById('pm-route-caption');
  if (!board || !output) return;
  const selected = document.getElementById('pm-route-template');
  const kind = selected && selected.value || 'project';
  const plan = pmCurrentRoutePlan && pmCurrentRoutePlan.kind === kind ? pmCurrentRoutePlan : pmRoutePlan(kind);
  plan.kind = kind;
  pmCurrentRoutePlan = plan;
  if (caption) caption.textContent = plan.title;
  board.innerHTML = '<div class="pm-route-track">' + plan.nodes.map(node => pmRouteNode(node[0], node[1], node[2], node[3])).join('') + '</div>';
  output.innerHTML = pmControlKv('Comando', plan.command)
    + pmControlKv('Salida esperada', plan.output)
    + pmControlKv('Proveedor', (pmCurrentSession() && pmCurrentSession().provider) || 'ollama-local')
    + pmControlKv('Instalacion', pmSelectedInstallPath());
}

function pmUpdateRouteLines() {
  return true;
}

function pmInitOpsConsole() {
  const build = document.getElementById('pm-route-build');
  const copy = document.getElementById('pm-route-copy');
  const template = document.getElementById('pm-route-template');
  if (build) build.addEventListener('click', () => pmBuildRoute(template && template.value || 'project'));
  if (copy) copy.addEventListener('click', () => copyText(JSON.stringify(pmCurrentRoutePlan || pmRoutePlan(template && template.value || 'project'), null, 2)));
  if (template) template.addEventListener('change', () => pmRenderRoute());
  pmRenderControl();
  pmRenderRoute();
}

pmInitOpsConsole();
