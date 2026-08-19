import { useMemo, useState, type FormEvent, type MouseEvent as ReactMouseEvent } from 'react';
import './provider-center.css';
import { friendlyErrorMessage } from '@/shared/friendly-error';
import { normalizeProviderBaseUrl } from '../../shared/providerRegistration';

export interface ProviderCenterProvider {
  id: string;
  name: string;
  description?: string;
  state?: string;
  configured?: boolean;
  modelCount?: number;
  models?: string[];
  raw?: unknown;
}

export interface ProviderCenterRouterEntry {
  id: string;
  label: string;
  provider?: string;
  bestFor?: string;
  available?: boolean;
  selected?: boolean;
  contextTokens?: number;
  raw?: unknown;
}

export interface ProviderCenterModuleProps {
  title?: string;
  subtitle?: string;
  frameworkLabel?: string;
  projectLabel?: string;
  scopeLabel?: string;
  providers: ProviderCenterProvider[];
  routerEntries: ProviderCenterRouterEntry[];
  routerAuto: boolean;
  routerSelectedCount: number;
  routerLastPick?: string;
  sessionModel?: string | null;
  onRefreshRouter?: () => void;
  onSetRouterAuto?: (enabled: boolean) => void;
  onToggleRouter: (key: string) => void;
  onInspectProvider?: (provider: ProviderCenterProvider) => void;
  onInspectRouterEntry?: (entry: ProviderCenterRouterEntry) => void;
  onProviderContextMenu?: (provider: ProviderCenterProvider, event: ReactMouseEvent<HTMLElement>) => void;
  onRouterEntryContextMenu?: (entry: ProviderCenterRouterEntry, event: ReactMouseEvent<HTMLElement>) => void;
  onPanelContextMenu?: (panel: 'providers' | 'router' | 'summary', event: ReactMouseEvent<HTMLElement>) => void;
  onRegisterProvider?: () => void;
  onRegisterModel?: () => void;
  onToggleProvider?: (provider: ProviderCenterProvider, enabled: boolean) => void;
  onConfigureProvider?: (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }) => Promise<void>;
  onSetSessionModel?: (modelKey: string | null) => Promise<void>;
}

function stateTone(state: string | undefined): 'good' | 'warn' | 'bad' | 'neutral' {
  const clean = String(state || '').toLowerCase();
  if (clean.includes('confirmed') || clean.includes('active') || clean.includes('ready')) return 'good';
  if (clean.includes('blocked') || clean.includes('error') || clean.includes('disabled')) return 'bad';
  if (clean.includes('degraded') || clean.includes('pending') || clean.includes('unknown')) return 'warn';
  return 'neutral';
}

interface ProviderFormState {
  providerId: string;
  providerName: string;
  enabled: boolean;
  base_url: string;
  api_key: string;
  model: string;
  models: string[];
}

interface ProviderPreset {
  title: string;
  description: string;
  registrationTitle: string;
  registrationMode: 'api-key' | 'login' | 'cli' | 'none';
  registrationSteps: string[];
  baseUrlLabel: string;
  baseUrlPlaceholder: string;
  apiKeyLabel: string;
  apiKeyPlaceholder: string;
  modelLabel: string;
  modelPlaceholder: string;
  showBaseUrl: boolean;
  showApiKey: boolean;
  showModel: boolean;
}

const DEFAULT_PRESET: ProviderPreset = {
  title: 'Proveedor genérico',
  description: 'Ajusta la conexión básica y el modelo por defecto.',
  registrationTitle: 'Registro',
  registrationMode: 'api-key',
  registrationSteps: ['Introduce la URL base', 'Añade tu API key o token', 'Guarda el modelo por defecto'],
  baseUrlLabel: 'URL base',
  baseUrlPlaceholder: 'http://127.0.0.1:11434',
  apiKeyLabel: 'API Key',
  apiKeyPlaceholder: 'sk-...',
  modelLabel: 'Modelo por defecto',
  modelPlaceholder: 'llama3.2:3b',
  showBaseUrl: true,
  showApiKey: true,
  showModel: true
};

const PROVIDER_PRESETS: Record<string, ProviderPreset> = {
  'ollama-local': {
    title: 'Ollama local',
    description: 'Usa el endpoint local de Ollama en tu máquina.',
    registrationTitle: 'Alta local',
    registrationMode: 'none',
    registrationSteps: ['Arranca Ollama', 'Selecciona la URL local', 'Elige un modelo disponible'],
    baseUrlLabel: 'URL local',
    baseUrlPlaceholder: 'http://127.0.0.1:11434',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'No hace falta',
    modelLabel: 'Modelo local',
    modelPlaceholder: 'llama3.2:3b',
    showBaseUrl: true,
    showApiKey: false,
    showModel: true
  },
  'ollama-cloud': {
    title: 'Ollama Cloud',
    description: 'Conexión remota a Ollama con credenciales.',
    registrationTitle: 'Acceso',
    registrationMode: 'api-key',
    registrationSteps: ['Introduce la URL cloud', 'Pega el token de acceso', 'Guarda el modelo cloud'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://ollama.com',
    apiKeyLabel: 'Token / API key',
    apiKeyPlaceholder: 'Bearer token',
    modelLabel: 'Modelo cloud',
    modelPlaceholder: 'gemma3:27b',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  anthropic: {
    title: 'Anthropic',
    description: 'Proveedor Anthropic con clave y modelo por defecto.',
    registrationTitle: 'Registro por API key',
    registrationMode: 'api-key',
    registrationSteps: ['Crea tu API key en Anthropic', 'Pégala en el campo seguro', 'Guarda el modelo preferido'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.anthropic.com',
    apiKeyLabel: 'API key',
    apiKeyPlaceholder: 'sk-ant-...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'claude-3-5-sonnet-latest',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  openai: {
    title: 'OpenAI',
    description: 'API OpenAI estándar o compatible.',
    registrationTitle: 'Registro por API key',
    registrationMode: 'api-key',
    registrationSteps: ['Genera una API key', 'Introduce la base URL si no es la estándar', 'Selecciona un modelo'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
    apiKeyLabel: 'API key',
    apiKeyPlaceholder: 'sk-...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'gpt-4o-mini',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  openrouter: {
    title: 'OpenRouter',
    description: 'Router externo con API key y modelo específico.',
    registrationTitle: 'Registro por API key',
    registrationMode: 'api-key',
    registrationSteps: ['Crea tu API key en OpenRouter', 'Añade el endpoint', 'Escoge el modelo de la ruta'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://openrouter.ai/api/v1',
    apiKeyLabel: 'API key',
    apiKeyPlaceholder: 'sk-or-...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'anthropic/claude-3.5-sonnet',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  codex: {
    title: 'Codex',
    description: 'Configuración del provider Codex.',
    registrationTitle: 'Registro / login',
    registrationMode: 'login',
    registrationSteps: ['Abre sesión en Codex CLI o añade tu API key', 'Verifica el estado de autenticación', 'Guarda el modelo para la sesión'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.openai.com/v1',
    apiKeyLabel: 'API key',
    apiKeyPlaceholder: 'sk-...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'gpt-4.1',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  copilot: {
    title: 'Copilot',
    description: 'Provider Copilot configurado con credenciales locales.',
    registrationTitle: 'Inicio de sesión',
    registrationMode: 'login',
    registrationSteps: ['Inicia sesión con GitHub Copilot CLI', 'Comprueba que la sesión esté activa', 'Guarda el modelo por defecto'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'https://api.githubcopilot.com',
    apiKeyLabel: 'Token',
    apiKeyPlaceholder: 'ghu_...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'gpt-4.1',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  },
  'cpp-local': {
    title: 'CPP local',
    description: 'Backend local con endpoint propio.',
    registrationTitle: 'Alta local',
    registrationMode: 'none',
    registrationSteps: ['Arranca el servidor local', 'Asegura la URL del endpoint', 'Selecciona el modelo compilado'],
    baseUrlLabel: 'URL base',
    baseUrlPlaceholder: 'http://127.0.0.1:8081',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'No hace falta',
    modelLabel: 'Modelo',
    modelPlaceholder: 'local-model',
    showBaseUrl: true,
    showApiKey: false,
    showModel: true
  },
  'opencode': {
    title: 'OpenCode',
    description: 'Provider local o remoto con endpoint configurable.',
    registrationTitle: 'Registro',
    registrationMode: 'api-key',
    registrationSteps: ['Configura el endpoint', 'Añade la API key si hace falta', 'Guarda el modelo del servidor'],
    baseUrlLabel: 'Base URL',
    baseUrlPlaceholder: 'http://127.0.0.1:3000',
    apiKeyLabel: 'API Key',
    apiKeyPlaceholder: 'opencode-...',
    modelLabel: 'Modelo',
    modelPlaceholder: 'default',
    showBaseUrl: true,
    showApiKey: true,
    showModel: true
  }
};

function getProviderPreset(providerId: string): ProviderPreset {
  return PROVIDER_PRESETS[providerId] || DEFAULT_PRESET;
}

function readString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function readModels(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

export function ProviderCenterModule(props: ProviderCenterModuleProps) {
  const [configForm, setConfigForm] = useState<ProviderFormState | null>(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);
  const [sessionSetting, setSessionSetting] = useState<string | null>(null);
  const [manualFieldsOpen, setManualFieldsOpen] = useState(false);

  const providerCount = props.providers.length;
  const selectedCount = props.routerSelectedCount;
  const currentProvider = useMemo(
    () => props.providers.find((provider) => provider.id === configForm?.providerId) || null,
    [props.providers, configForm?.providerId]
  );
  const configPreset = getProviderPreset(configForm?.providerId || '');
  const currentProviderModels = currentProvider?.models || [];
  const configUrlCandidates = useMemo(() => {
    if (!configForm) return [];
    const raw = currentProvider?.raw as Record<string, unknown> | undefined;
    const values = [
      readString(raw?.base_url || raw?.url || raw?.endpoint || ''),
      readString(raw?.default_base_url || ''),
      configForm.base_url,
    ].map((item) => normalizeProviderBaseUrl(configForm.providerId, item)).filter(Boolean);
    return Array.from(new Set(values));
  }, [configForm, currentProvider?.raw]);
  const configModelCandidates = useMemo(() => {
    if (!configForm) return [];
    const values = [
      ...currentProviderModels,
      configForm.model,
    ].map((item) => item.trim()).filter(Boolean);
    return Array.from(new Set(values));
  }, [configForm, currentProviderModels]);

  function openConfigForm(provider: ProviderCenterProvider) {
    const raw = provider.raw as Record<string, unknown> | undefined;
    const preset = getProviderPreset(provider.id);
    const configuredUrl = readString(raw?.base_url || raw?.url || raw?.endpoint || '');
    const defaultUrl = readString(raw?.default_base_url || '') || preset.baseUrlPlaceholder;
    setConfigForm({
      providerId: provider.id,
      providerName: provider.name,
      enabled: typeof raw?.enabled === 'boolean' ? raw.enabled : Boolean(provider.configured),
      base_url: normalizeProviderBaseUrl(provider.id, configuredUrl, defaultUrl),
      api_key: readString(raw?.api_key || raw?.token || ''),
      model: readString(raw?.default_model || raw?.model || ''),
      models: readModels(raw?.models || raw?.available_models || provider.models || []),
    });
    setManualFieldsOpen(!provider.configured);
    setConfigError(null);
  }

  function closeConfigForm() {
    if (configSaving) return;
    setConfigError(null);
    setConfigForm(null);
  }

  async function submitConfigForm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!configForm || !props.onConfigureProvider) return;
    setConfigSaving(true);
    setConfigError(null);
    try {
      await props.onConfigureProvider(configForm.providerId, {
        enabled: configForm.enabled,
        ...(configForm.base_url ? {
          base_url: normalizeProviderBaseUrl(configForm.providerId, configForm.base_url)
        } : {}),
        ...(configForm.api_key ? { api_key: configForm.api_key.trim() } : {}),
        ...(configForm.model ? { model: configForm.model.trim() } : {}),
      });
      setConfigForm(null);
      props.onRefreshRouter?.();
    } catch (error) {
      setConfigError(friendlyErrorMessage(error, 'No se pudo guardar el proveedor'));
    } finally {
      setConfigSaving(false);
    }
  }

  async function handleSetSessionModel(entry: ProviderCenterRouterEntry) {
    if (!props.onSetSessionModel) return;
    const key = entry.id;
    const isCurrent = props.sessionModel === key;
    setSessionSetting(key);
    try {
      await props.onSetSessionModel(isCurrent ? null : key);
    } finally {
      setSessionSetting(null);
    }
  }

  return (
    <section
      className="provider-center"
      aria-labelledby="provider-center-title"
      onContextMenu={(event) => props.onPanelContextMenu?.('summary', event)}
    >
      <header className="provider-center__header">
        <div className="provider-center__copy">
          <span className="provider-center__eyebrow">Proveedores y modelos</span>
          <h3 id="provider-center-title">{props.title || 'Centro de proveedores'}</h3>
          <p>{props.subtitle || 'Ver, seleccionar, activar y revisar el catálogo disponible sin acoplarlo al shell principal.'}</p>
        </div>
        <div className="provider-center__meta">
          <span>{props.frameworkLabel || 'Framework no confirmado'}</span>
          <span>{props.projectLabel || 'Proyecto no confirmado'}</span>
          <span>{props.scopeLabel || 'Scope no confirmado'}</span>
        </div>
      </header>

      <div className="provider-center__stats">
        <article className="provider-center__stat">
          <span>Proveedores</span>
          <strong>{providerCount}</strong>
          <small>{props.onConfigureProvider ? 'Configuración disponible' : 'Solo inspección'}</small>
        </article>
        <article className="provider-center__stat">
          <span>Modelos activos</span>
          <strong>{selectedCount}</strong>
          <small>{props.routerAuto ? 'Auto-router activo' : 'Auto-router pausado'}</small>
        </article>
        <article className="provider-center__stat">
          <span>Sesión / Último uso</span>
          <strong style={{ fontSize: 12 }}>{props.sessionModel ? props.sessionModel.split('/').pop() : (props.routerLastPick || '—')}</strong>
          <small>{props.sessionModel ? 'Override de sesión activo' : 'Sin override'}</small>
        </article>
      </div>

      {configForm && (
        <div className="provider-center__overlay" role="presentation" onClick={closeConfigForm}>
          <div className="provider-center__drawer" role="dialog" aria-modal="true" aria-labelledby="provider-config-title" onClick={(e) => e.stopPropagation()}>
            <div className="provider-center__drawer-head">
              <div className="provider-center__drawer-copy">
                <span className="provider-center__eyebrow">Configurar proveedor</span>
                <h4 id="provider-config-title">{configForm.providerName}</h4>
                <p>{configPreset.description}</p>
              </div>
              <button type="button" className="provider-center__ghost" onClick={closeConfigForm}>✕ Cerrar</button>
            </div>

            <div className="provider-center__chips">
              <span className="provider-center__chip">ID: {configForm.providerId}</span>
              <span className="provider-center__chip">{configPreset.title}</span>
              <span className={`provider-center__chip tone-${stateTone(currentProvider?.state)} `}>{currentProvider?.configured ? 'Ya configurado' : 'Pendiente'}</span>
              <span className="provider-center__chip">{configPreset.registrationMode === 'login' ? 'Login' : configPreset.registrationMode === 'api-key' ? 'API key' : 'Local'}</span>
            </div>

            <div className="provider-center__drawer-body">
              <aside className="provider-center__drawer-side">
                <section className="provider-center__stack">
                  <div className="provider-center__section-title">
                    <span className="provider-center__eyebrow">{configPreset.registrationTitle}</span>
                    <strong>{configPreset.registrationMode === 'login' ? 'Inicio de sesión' : configPreset.registrationMode === 'api-key' ? 'Registro por API' : 'Registro local'}</strong>
                  </div>
                  <ol className="provider-center__steps">
                    {configPreset.registrationSteps.map((step) => <li key={step}>{step}</li>)}
                  </ol>
                  {configPreset.registrationMode === 'login' && (
                    <div className="provider-center__tip">
                        En algunos providers esto se completa con CLI (por ejemplo Copilot/Codex). Aquí solo registramos la sesión activa o el token real detectado.
                    </div>
                  )}
                </section>

                <section className="provider-center__stack">
                  <div className="provider-center__section-title">
                      <span className="provider-center__eyebrow">Datos reales</span>
                      <strong>Lo que ya conoce el backend</strong>
                  </div>
                    <div className="provider-center__facts">
                      <div className="provider-center__fact">
                        <span>URL</span>
                        <strong>{configForm.base_url || 'No configurada'}</strong>
                      </div>
                      <div className="provider-center__fact">
                        <span>Modelo</span>
                        <strong>{configForm.model || 'Sin modelo'}</strong>
                      </div>
                      <div className="provider-center__fact">
                        <span>Clave</span>
                        <strong>{configForm.api_key ? 'Guardada' : 'No guardada'}</strong>
                      </div>
                    </div>
                </section>

                <section className="provider-center__stack">
                    <div className="provider-center__section-title">
                      <span className="provider-center__eyebrow">Selección real</span>
                      <strong>{configUrlCandidates.length ? 'Endpoint y modelo' : 'Sin datos seleccionables'}</strong>
                    </div>
                    <div className="provider-center__selection-group">
                      <span className="provider-center__selection-label">Endpoint</span>
                      <div className="provider-center__model-list">
                        {configUrlCandidates.length ? configUrlCandidates.map((url) => (
                          <button
                            key={url}
                            type="button"
                            className={`provider-center__model-chip ${configForm.base_url === url ? 'is-active' : ''}`}
                            onClick={() => setConfigForm((f) => (f ? { ...f, base_url: url } : f))}
                          >
                            {url}
                          </button>
                        )) : (
                          <div className="provider-center__empty">No hay endpoint detectado.</div>
                        )}
                      </div>
                    </div>

                    <div className="provider-center__selection-group">
                      <span className="provider-center__selection-label">Modelo</span>
                      <div className="provider-center__model-list">
                        {configModelCandidates.length ? configModelCandidates.map((model) => (
                          <button
                            key={model}
                            type="button"
                            className={`provider-center__model-chip ${configForm.model === model ? 'is-active' : ''}`}
                            onClick={() => setConfigForm((f) => (f ? { ...f, model } : f))}
                          >
                            {model}
                          </button>
                        )) : (
                          <div className="provider-center__empty">No hay modelo detectado.</div>
                        )}
                      </div>
                    </div>

                    {configPreset.showApiKey && (
                      <div className="provider-center__selection-group">
                        <span className="provider-center__selection-label">Clave real</span>
                        <div className="provider-center__chips">
                          <span className={`provider-center__chip tone-${configForm.api_key ? 'good' : 'warn'}`}>
                            {configForm.api_key ? 'Clave presente' : 'Falta clave'}
                          </span>
                          <button
                            type="button"
                            className="provider-center__secondary"
                            onClick={() => setManualFieldsOpen((current) => !current)}
                          >
                            {manualFieldsOpen ? 'Ocultar edición manual' : 'Editar clave / endpoint manualmente'}
                          </button>
                        </div>
                      </div>
                    )}
                </section>
              </aside>

              <form className="provider-center__form" onSubmit={submitConfigForm}>
                <label className="provider-center__field provider-center__field--toggle">
                    <span>Estado</span>
                    <div className="provider-center__toggle">
                      <input
                        type="checkbox"
                        checked={configForm.enabled}
                        onChange={(e) => setConfigForm((f) => (f ? { ...f, enabled: e.target.checked } : f))}
                      />
                      <small>Habilitar este proveedor para esta instalación</small>
                    </div>
                </label>

                <div className="provider-center__manual-toggle">
                    <button
                      type="button"
                      className="provider-center__ghost"
                      onClick={() => setManualFieldsOpen((current) => !current)}
                    >
                      {manualFieldsOpen ? 'Ocultar campos manuales' : 'Mostrar campos manuales'}
                    </button>
                    <small>Solo aparece si no hay datos reales suficientes.</small>
                </div>

                {manualFieldsOpen && configPreset.showBaseUrl && (
                    <label className="provider-center__field">
                      <span>{configPreset.baseUrlLabel}</span>
                      <input
                        className="provider-center__input"
                        type="url"
                        value={configForm.base_url}
                        placeholder={configPreset.baseUrlPlaceholder}
                        onChange={(e) => setConfigForm((f) => (f ? { ...f, base_url: e.target.value } : f))}
                      />
                    </label>
                )}

                {manualFieldsOpen && configPreset.showApiKey && (
                    <label className="provider-center__field">
                      <span>{configPreset.apiKeyLabel}</span>
                      <input
                        className="provider-center__input"
                        type="password"
                        value={configForm.api_key}
                        placeholder={configPreset.apiKeyPlaceholder}
                        onChange={(e) => setConfigForm((f) => (f ? { ...f, api_key: e.target.value } : f))}
                      />
                    </label>
                )}

                {manualFieldsOpen && configPreset.showModel && (
                    <label className="provider-center__field">
                      <span>{configPreset.modelLabel}</span>
                      <input
                        className="provider-center__input"
                        type="text"
                        value={configForm.model}
                        placeholder={configPreset.modelPlaceholder}
                        onChange={(e) => setConfigForm((f) => (f ? { ...f, model: e.target.value } : f))}
                      />
                    </label>
                )}

                {configError && <div className="provider-center__error">{configError}</div>}

                <div className="provider-center__drawer-foot">
                    <small className="provider-center__help">
                      {configPreset.showApiKey ? 'La clave solo se pide si no hay una detectada o si quieres cambiarla.' : 'No hace falta API key para este proveedor.'}
                    </small>
                    <div className="provider-center__actions">
                      <button type="button" className="provider-center__ghost" onClick={closeConfigForm} disabled={configSaving}>Cancelar</button>
                      <button type="submit" className="provider-center__ghost is-active" disabled={configSaving}>
                      {configSaving ? 'Guardando...' : 'Guardar cambios'}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      <div className="provider-center__grid">
        {/* Providers panel */}
        <article
          className="provider-center__panel"
          onContextMenu={(event) => props.onPanelContextMenu?.('providers', event)}
        >
          <div className="provider-center__panel-head">
            <div>
              <span className="provider-center__eyebrow">Catálogo</span>
              <strong>{providerCount ? `${providerCount} proveedores` : 'Sin proveedores'}</strong>
            </div>
          </div>

          <div className="provider-center__list">
            {props.providers.length ? props.providers.map((provider) => (
              <article
                key={provider.id}
                className="provider-center__row"
                onContextMenu={(event) => props.onProviderContextMenu?.(provider, event)}
              >
                <button
                  type="button"
                  className="provider-center__row-main"
                  onClick={() => props.onInspectProvider?.(provider)}
                >
                  <span className={`provider-center__pill tone-${stateTone(provider.state)}`}>{provider.configured ? 'Activo' : 'Inactivo'}</span>
                  <span className="provider-center__row-copy">
                    <strong>{provider.name}</strong>
                    <small>{provider.description || provider.state || 'Sin descripción'}</small>
                    {provider.models?.length ? (
                      <span className="provider-center__row-tags">
                        {provider.models.slice(0, 3).map((model) => <span key={model} className="provider-center__row-tag">{model}</span>)}
                        {provider.models.length > 3 && <span className="provider-center__row-tag">+{provider.models.length - 3}</span>}
                      </span>
                    ) : null}
                  </span>
                  <span className="provider-center__row-meta">{provider.modelCount ?? 0} modelos</span>
                </button>
                {props.onConfigureProvider && (
                  <button
                    type="button"
                    className="provider-center__secondary"
                    onClick={() => openConfigForm(provider)}
                  >
                    Ajustar
                  </button>
                )}
              </article>
            )) : (
              <div className="provider-center__empty">No hay proveedores cargados.</div>
            )}
          </div>
        </article>

        {/* Router / Models panel */}
        <article
          className="provider-center__panel"
          onContextMenu={(event) => props.onPanelContextMenu?.('router', event)}
        >
          <div className="provider-center__panel-head">
            <div>
              <span className="provider-center__eyebrow">Router / Orquestador</span>
              <strong>{selectedCount ? `${selectedCount} seleccionados` : 'Sin selección activa'}</strong>
            </div>
            <div className="provider-center__actions">
              {props.onRefreshRouter && (
                <button type="button" className="provider-center__ghost" onClick={props.onRefreshRouter}>
                  Refrescar
                </button>
              )}
              {props.onSetRouterAuto && (
                <button
                  type="button"
                  className={`provider-center__ghost ${props.routerAuto ? 'is-active' : ''}`}
                  onClick={() => props.onSetRouterAuto?.(!props.routerAuto)}
                >
                  Auto {props.routerAuto ? 'ON' : 'OFF'}
                </button>
              )}
            </div>
          </div>

          {props.sessionModel && (
            <div style={{ padding: '8px 12px', borderRadius: 10, background: 'rgba(103,136,247,.12)', border: '1px solid rgba(103,136,247,.3)', fontSize: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <span>
                <span style={{ color: 'var(--text-3)' }}>Sesión: </span>
                <strong>{props.sessionModel}</strong>
              </span>
              {props.onSetSessionModel && (
                <button
                  type="button"
                  className="provider-center__ghost"
                  style={{ fontSize: 11, padding: '0 8px', minHeight: 26 }}
                  onClick={() => void props.onSetSessionModel?.(null)}
                >
                  ✕ Quitar override
                </button>
              )}
            </div>
          )}

          <div className="provider-center__list">
            {props.routerEntries.length ? props.routerEntries.map((entry) => {
              const isSessionModel = props.sessionModel === entry.id;
              const isSetting = sessionSetting === entry.id;
              return (
                <article
                  key={entry.id}
                  className="provider-center__row"
                  style={isSessionModel ? { outline: '1px solid rgba(103,136,247,.4)', borderRadius: 12 } : undefined}
                  onContextMenu={(event) => props.onRouterEntryContextMenu?.(entry, event)}
                >
                  <button
                    type="button"
                    className="provider-center__row-main"
                    onClick={() => props.onInspectRouterEntry?.(entry)}
                  >
                    <span className={`provider-center__pill tone-${entry.selected ? 'good' : entry.available === false ? 'bad' : 'warn'}`}>
                      {isSessionModel ? 'Sesión' : entry.selected ? 'Router' : entry.available === false ? 'No disp.' : 'Disponible'}
                    </span>
                    <span className="provider-center__row-copy">
                      <strong>{entry.label}</strong>
                      <small>{entry.bestFor || entry.provider || 'Sin descripción'}</small>
                    </span>
                    <span className="provider-center__row-meta">{entry.contextTokens ? `${Math.round(entry.contextTokens / 1000)}k ctx` : '—'}</span>
                  </button>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <button
                      type="button"
                      className="provider-center__secondary"
                      onClick={() => props.onToggleRouter(entry.id)}
                    >
                      {entry.selected ? 'Quitar' : 'Router'}
                    </button>
                    {props.onSetSessionModel && (
                      <button
                        type="button"
                        className={`provider-center__secondary ${isSessionModel ? 'is-active' : ''}`}
                        style={{ fontSize: 11 }}
                        disabled={isSetting}
                        onClick={() => void handleSetSessionModel(entry)}
                      >
                        {isSetting ? '...' : isSessionModel ? '✓ Sesión' : 'Sesión'}
                      </button>
                    )}
                  </div>
                </article>
              );
            }) : (
              <div className="provider-center__empty">No hay modelos de router disponibles.</div>
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
