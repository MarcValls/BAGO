const CONFIG_KEY = 'bago.android.mini.config.v1';
const SESSION_KEY_PREFIX = 'bago.android.mini.key.';

const PRESETS = {
  openrouter: {
    endpoint: 'https://openrouter.ai/api/v1',
    model: 'openai/gpt-4o-mini',
    envKey: 'OPENROUTER_API_KEY',
  },
  codex: {
    endpoint: 'https://api.openai.com/v1',
    model: 'gpt-5.4-mini',
    envKey: 'OPENAI_API_KEY',
  },
};

const providerSelect = document.getElementById('provider-select');
const modelInput = document.getElementById('model-input');
const endpointInput = document.getElementById('endpoint-input');
const apiKeyInput = document.getElementById('api-key-input');
const statusBox = document.getElementById('status-box');
const promptInput = document.getElementById('prompt-input');
const responseBox = document.getElementById('response-box');
const termuxBox = document.getElementById('termux-box');
const layersBox = document.getElementById('layers-box');
const layersJsonInput = document.getElementById('layers-json-input');
let lastNetworkLayer = {
  ok: false,
  details: { reachable: false, reason: 'Sin prueba de red.' },
  actions: ['Ejecuta "Probar conexion" para validar red/provider.'],
};

function readConfig() {
  try {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (!raw) return { provider: 'openrouter', model: PRESETS.openrouter.model, endpoint: PRESETS.openrouter.endpoint };
    const parsed = JSON.parse(raw);
    return {
      provider: PRESETS[parsed.provider] ? parsed.provider : 'openrouter',
      model: String(parsed.model || '').trim() || PRESETS.openrouter.model,
      endpoint: String(parsed.endpoint || '').trim() || PRESETS.openrouter.endpoint,
    };
  } catch (_e) {
    return { provider: 'openrouter', model: PRESETS.openrouter.model, endpoint: PRESETS.openrouter.endpoint };
  }
}

function writeConfig() {
  const cfg = {
    provider: providerSelect.value,
    model: modelInput.value.trim(),
    endpoint: endpointInput.value.trim().replace(/\/+$/, ''),
  };
  localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
  renderTermux();
}

function sessionKeyName(provider) {
  return `${SESSION_KEY_PREFIX}${provider}`;
}

function setSessionApiKey(provider, value) {
  if (!value) {
    sessionStorage.removeItem(sessionKeyName(provider));
    return;
  }
  sessionStorage.setItem(sessionKeyName(provider), value);
}

function getSessionApiKey(provider) {
  return sessionStorage.getItem(sessionKeyName(provider)) || '';
}

function setStatus(message, ok = true) {
  statusBox.textContent = message;
  statusBox.className = `status ${ok ? 'ok' : 'bad'}`;
}

function summarizeLayer(name, layer) {
  const state = layer && layer.ok ? 'ok' : 'pendiente';
  const details = layer && layer.details ? JSON.stringify(layer.details) : '{}';
  return `- ${name}: ${state}\n  detalles: ${details}`;
}

function renderLayers(payload, source = 'web') {
  if (!layersBox) return;
  const layers = payload && payload.layers ? payload.layers : {};
  const names = Object.keys(layers);
  if (names.length === 0) {
    layersBox.textContent = 'Sin diagnostico de capas.';
    return;
  }
  const allOk = names.every(name => !!layers[name].ok);
  const lines = [
    `Fuente: ${source}`,
    `Estado global: ${allOk ? 'OK' : 'PENDIENTE'}`,
    ...names.map(name => summarizeLayer(name, layers[name])),
  ];
  const actions = payload.next_actions || [];
  if (actions.length) {
    lines.push('Acciones recomendadas:');
    for (const step of actions) lines.push(`  - ${step}`);
  }
  layersBox.textContent = lines.join('\n');
}

function layerSecurityWeb() {
  const localStorageHasKeyMaterial = Object.keys(localStorage).some(key => key.includes('api_key') || key.includes('OPENAI') || key.includes('OPENROUTER'));
  const sessionScoped = Object.keys(sessionStorage).some(key => key.startsWith(SESSION_KEY_PREFIX));
  const ok = !localStorageHasKeyMaterial;
  const actions = [];
  if (localStorageHasKeyMaterial) actions.push('Mover credenciales de localStorage a sessionStorage o CLI.');
  if (!sessionScoped) actions.push('Guardar API key de sesion para operar provider.');
  return {
    ok,
    details: { localStorage_has_key_material: localStorageHasKeyMaterial, session_key_present: sessionScoped },
    actions,
  };
}

function buildWebLayers() {
  const provider = providerSelect.value;
  const endpoint = endpointInput.value.trim();
  const model = modelInput.value.trim();
  const key = apiKeyInput.value.trim() || getSessionApiKey(provider);
  const isAndroid = /Android/i.test(navigator.userAgent || '');
  const layers = {
    layer_runtime: {
      ok: isAndroid,
      details: { android_user_agent: isAndroid, termux_detected: /Termux|com\.termux/i.test(navigator.userAgent || '') },
      actions: isAndroid ? [] : ['Abrir este gestor desde un dispositivo Android.'],
    },
    layer_provider: {
      ok: !!provider && !!endpoint && !!model && !!key,
      details: { provider, endpoint, model, key_present: !!key },
      actions: [
        ...(!endpoint ? ['Definir endpoint del provider.'] : []),
        ...(!model ? ['Definir modelo objetivo.'] : []),
        ...(!key ? [`Definir ${PRESETS[provider].envKey} en sesion.`] : []),
      ],
    },
    layer_network: lastNetworkLayer,
    layer_security: layerSecurityWeb(),
    layer_ui: {
      ok: true,
      details: { manager_android_loaded: true },
      actions: [],
    },
  };
  const nextActions = [];
  for (const name of Object.keys(layers)) {
    for (const action of layers[name].actions || []) {
      if (!nextActions.includes(action)) nextActions.push(action);
    }
  }
  return { layers, next_actions: nextActions };
}

function refreshLayersWeb() {
  renderLayers(buildWebLayers(), 'web-local');
}

function loadLayersFromCliJson() {
  const raw = (layersJsonInput && layersJsonInput.value || '').trim();
  if (!raw) {
    setStatus('Pega primero el JSON de `bago android layers --json`.', false);
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    const payload = parsed.layers ? parsed : parsed.layers_report ? parsed.layers_report : null;
    if (!payload || !payload.layers) {
      setStatus('JSON sin estructura de capas.', false);
      return;
    }
    renderLayers(payload, 'cli-json');
    setStatus('Capas cargadas desde CLI.', true);
  } catch (_err) {
    setStatus('JSON CLI invalido.', false);
  }
}

function providerHeaders(provider, key) {
  const headers = {
    Authorization: `Bearer ${key}`,
    'Content-Type': 'application/json',
  };
  if (provider === 'openrouter') {
    headers['HTTP-Referer'] = location.origin || 'https://bago.local';
    headers['X-Title'] = 'BAGO Android Mini';
  }
  return headers;
}

function mapHttpError(status) {
  if (status === 401) return '401: clave invalida o sin permisos.';
  if (status === 403) return '403: acceso denegado por el provider.';
  if (status === 404) return '404: endpoint/modelo no encontrado.';
  if (status === 429) return '429: limite de tasa alcanzado.';
  if (status >= 500) return `${status}: provider temporalmente no disponible.`;
  return `${status}: error no esperado del provider.`;
}

async function readJsonSafe(response) {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (_e) {
    return { raw: text };
  }
}

async function testHealth() {
  const provider = providerSelect.value;
  const endpoint = endpointInput.value.trim().replace(/\/+$/, '');
  const key = apiKeyInput.value.trim() || getSessionApiKey(provider);
  if (!key) {
    setStatus(`Falta ${PRESETS[provider].envKey} en esta sesion.`, false);
    return;
  }
  setStatus('Probando conexion...');
  try {
    const response = await fetch(`${endpoint}/models`, {
      method: 'GET',
      headers: providerHeaders(provider, key),
    });
    if (!response.ok) {
      lastNetworkLayer = {
        ok: false,
        details: { reachable: false, status: response.status },
        actions: ['Revisar conectividad o credenciales del provider.'],
      };
      refreshLayersWeb();
      setStatus(mapHttpError(response.status), false);
      return;
    }
    const payload = await readJsonSafe(response);
    const count = Array.isArray(payload.data) ? payload.data.length : 0;
    lastNetworkLayer = {
      ok: true,
      details: { reachable: true, models_visible: count },
      actions: [],
    };
    refreshLayersWeb();
    setStatus(`Conexion OK. Modelos visibles: ${count}.`, true);
  } catch (_err) {
    lastNetworkLayer = {
      ok: false,
      details: { reachable: false, reason: 'network-or-cors' },
      actions: ['Verificar red Android, DNS o restricciones CORS.'],
    };
    refreshLayersWeb();
    setStatus('Fallo de red/CORS. Revisa conectividad o endpoint.', false);
  }
}

async function sendPrompt() {
  const provider = providerSelect.value;
  const endpoint = endpointInput.value.trim().replace(/\/+$/, '');
  const model = modelInput.value.trim();
  const key = apiKeyInput.value.trim() || getSessionApiKey(provider);
  const prompt = promptInput.value.trim();
  if (!key) {
    setStatus(`Falta ${PRESETS[provider].envKey} en esta sesion.`, false);
    return;
  }
  if (!prompt) {
    setStatus('Escribe un prompt antes de enviar.', false);
    return;
  }
  responseBox.textContent = 'Consultando provider...';
  setStatus('Enviando prompt...');
  try {
    const payload = {
      model,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.2,
    };
    const response = await fetch(`${endpoint}/chat/completions`, {
      method: 'POST',
      headers: providerHeaders(provider, key),
      body: JSON.stringify(payload),
    });
    const body = await readJsonSafe(response);
    if (!response.ok) {
      responseBox.textContent = JSON.stringify(body, null, 2);
      setStatus(mapHttpError(response.status), false);
      return;
    }
    const content = body?.choices?.[0]?.message?.content || '';
    responseBox.textContent = content || JSON.stringify(body, null, 2);
    setStatus('Respuesta recibida.', true);
  } catch (_err) {
    responseBox.textContent = 'Error de red/CORS al llamar al provider.';
    setStatus('No se pudo completar la llamada.', false);
  }
}

function renderTermux() {
  const provider = providerSelect.value;
  const model = modelInput.value.trim();
  const envKey = PRESETS[provider].envKey;
  termuxBox.textContent = [
    '# Android / Termux',
    'pkg update -y && pkg install -y python git',
    '# En la raiz de BAGO:',
    `bago android init --provider ${provider} --model ${model}`,
    `export ${envKey}='<tu_clave>'`,
    `bago llm start --provider ${provider} --model ${model} --dry-run`,
  ].join('\n');
}

function syncPreset(forceDefaults = false) {
  const provider = providerSelect.value;
  const preset = PRESETS[provider];
  if (forceDefaults || !modelInput.value.trim()) modelInput.value = preset.model;
  if (forceDefaults || !endpointInput.value.trim()) endpointInput.value = preset.endpoint;
  apiKeyInput.value = getSessionApiKey(provider);
  renderTermux();
}

function copyTermux() {
  const text = termuxBox.textContent || '';
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(
      () => setStatus('Comandos copiados.', true),
      () => setStatus('No se pudo copiar al portapapeles.', false),
    );
    return;
  }
  setStatus('Portapapeles no disponible en este navegador.', false);
}

function init() {
  const cfg = readConfig();
  providerSelect.value = cfg.provider;
  modelInput.value = cfg.model;
  endpointInput.value = cfg.endpoint;
  syncPreset(false);

  document.getElementById('save-config-btn').addEventListener('click', () => {
    writeConfig();
    setStatus('Configuracion guardada (sin API key).', true);
  });
  document.getElementById('health-btn').addEventListener('click', testHealth);
  document.getElementById('send-btn').addEventListener('click', sendPrompt);
  document.getElementById('save-key-btn').addEventListener('click', () => {
    const provider = providerSelect.value;
    const key = apiKeyInput.value.trim();
    setSessionApiKey(provider, key);
    setStatus(key ? 'API key guardada solo en esta sesion.' : 'API key vacia.', !!key);
  });
  document.getElementById('clear-key-btn').addEventListener('click', () => {
    const provider = providerSelect.value;
    setSessionApiKey(provider, '');
    apiKeyInput.value = '';
    setStatus('Clave eliminada de la sesion.', true);
  });
  document.getElementById('copy-termux-btn').addEventListener('click', copyTermux);
  providerSelect.addEventListener('change', () => syncPreset(true));
  document.getElementById('layers-refresh-btn').addEventListener('click', refreshLayersWeb);
  document.getElementById('layers-load-cli-btn').addEventListener('click', loadLayersFromCliJson);
  refreshLayersWeb();
}

init();
