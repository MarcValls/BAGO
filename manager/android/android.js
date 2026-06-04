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
      setStatus(mapHttpError(response.status), false);
      return;
    }
    const payload = await readJsonSafe(response);
    const count = Array.isArray(payload.data) ? payload.data.length : 0;
    setStatus(`Conexion OK. Modelos visibles: ${count}.`, true);
  } catch (_err) {
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
}

init();
