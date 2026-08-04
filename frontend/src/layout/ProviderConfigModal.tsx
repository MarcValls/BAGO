// ProviderConfigModal.tsx
// Modal de configuración de proveedores. Reacciona al auth_kind para
// mostrar los campos correctos. Permite listar y marcar modelos activos
// tras guardar la configuración.

import { useEffect, useState } from 'react';
import type { BagoClient } from '../api/client';
import { ProviderDescriptor } from '../shared/provider-config';
import { Icon } from '../shared/Icon';
import { normalizeProviderModels } from '../shared/providerModels';
import { normalizeProviderBaseUrl } from '../shared/providerRegistration';
import { useDialogAccessibility } from '@/lib/useDialogAccessibility';

interface Props {
  descriptor: ProviderDescriptor;
  client: BagoClient;
  onClose: () => void;
  onSave: (cfg: { enabled: boolean; base_url?: string; api_key?: string; model?: string }) => Promise<void>;
  onDetectCli?: (tool: 'codex' | 'copilot') => Promise<{ installed: boolean; path: string | null; install_hint: string }>;
  // Estado inicial (lo que el backend ya tiene guardado)
  initial?: {
    enabled?: boolean;
    base_url?: string;
    api_key?: string;
    default_model?: string;
    has_secret?: boolean;
    models?: string[];
  };
}

export function ProviderConfigModal({ descriptor, client, onClose, onSave, onDetectCli, initial }: Props) {
  const [enabled, setEnabled] = useState(initial?.enabled ?? descriptor.enabled);
  const [baseUrl, setBaseUrl] = useState(() =>
    normalizeProviderBaseUrl(descriptor.provider_id, initial?.base_url, descriptor.base_url)
  );
  const [apiKey, setApiKey] = useState(initial?.api_key ?? '');
  const [model, setModel] = useState(initial?.default_model ?? '');
  const [credentialsRef, setCredentialsRef] = useState('');
  const [cliPath, setCliPath] = useState<string | null>(null);
  const [cliInstalled, setCliInstalled] = useState<boolean | null>(null);
  const [cliHint, setCliHint] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // ── Modelos disponibles / activos ──
  const [availableModels, setAvailableModels] = useState<string[]>(initial?.models ?? []);
  const [activeModels, setActiveModels] = useState<Set<string>>(new Set());
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [savingModels, setSavingModels] = useState(false);
  const [discoverySource, setDiscoverySource] = useState<string>('session-manager');
  const dialogRef = useDialogAccessibility<HTMLDivElement>(true, onClose, { closeDisabled: saving || savingModels });

  // Detección de CLI automática para auth_delegated_runtime
  useEffect(() => {
    if (descriptor.auth_kind !== 'auth_delegated_runtime' || !onDetectCli) return;
    const tool: 'codex' | 'copilot' = descriptor.provider_id === 'codex' ? 'codex' : 'copilot';
    void onDetectCli(tool).then((res) => {
      setCliInstalled(res.installed);
      setCliPath(res.path);
      setCliHint(res.install_hint);
    });
  }, [descriptor.provider_id, descriptor.auth_kind, onDetectCli]);

  // Cargar modelos activos al abrir (para tenerlos como base)
  useEffect(() => {
    void client.getActiveProviderModels(descriptor.provider_id)
      .then((data) => {
        if (Array.isArray(data.active_models)) {
          setActiveModels(new Set(data.active_models.map(String)));
        }
      })
      .catch(() => {});
  }, [client, descriptor.provider_id]);

  useEffect(() => {
    void loadModels();
  }, [client, descriptor.provider_id]);

  async function loadModels(): Promise<boolean> {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const data = await client.getModels(descriptor.provider_id);
      if (data.ok === false) {
        throw new Error(String(data.error || 'No se pudo validar el catálogo del proveedor'));
      }
      const entries = normalizeProviderModels(data);
      setAvailableModels(entries.map((entry) => entry.id));
      setDiscoverySource(String(data.models_source || data.discovery_source || 'session-manager'));
      if (!model) {
        const selected = String(data.selected_model || data.effective_model || '').trim();
        if (selected) setModel(selected);
      }
      return true;
    } catch (e) {
      setModelsError(String(e));
      return false;
    } finally {
      setModelsLoading(false);
    }
  }

  async function saveActiveModels() {
    setSavingModels(true);
    setModelsError(null);
    try {
      const data = await client.setActiveProviderModels(descriptor.provider_id, Array.from(activeModels));
      if (data.ok === false) {
        setModelsError(String(data.error || 'No se pudo guardar la selección'));
      }
    } catch (e) {
      setModelsError(String(e));
    } finally {
      setSavingModels(false);
    }
  }

  function toggleModel(name: string) {
    setActiveModels((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  // Advertencia de loopback para auth_none_local
  const isLoopback = /^https?:\/\/(127\.|localhost)/i.test(baseUrl);
  const showLoopbackWarning =
    descriptor.auth_kind === 'auth_none_local' && baseUrl && !isLoopback;

  // Avisos por auth_kind
  const showOAuthPending = descriptor.auth_kind === 'auth_oauth_browser';
  const showIamPending = descriptor.auth_kind === 'auth_iam_cloud' || descriptor.auth_kind === 'auth_wif_workload';
  const showDeviceFlowPending = descriptor.auth_kind === 'auth_device_flow';
  const showOpenAICompat = descriptor.auth_kind === 'auth_openai_compat';

  const save = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onSave({
        enabled,
        base_url: normalizeProviderBaseUrl(descriptor.provider_id, baseUrl, descriptor.base_url) || undefined,
        api_key: apiKey || undefined,
        model: model || undefined
      });
      const catalogValidated = await loadModels();
      if (catalogValidated) {
        setSaved(true);
      } else {
        setError('Registro guardado, pero el proveedor no pudo validar su catálogo. Revisa URL y credenciales.');
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="provider-config-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !saving && !savingModels) onClose(); }}>
      <div ref={dialogRef} tabIndex={-1} className="provider-config-modal" role="dialog" aria-modal="true" aria-label={`Configurar ${descriptor.label}`}>
        <header className="provider-config-modal-head">
          <div>
            <span className="provider-config-modal-eyebrow">{descriptor.protocol.replace('protocol_', '')}</span>
            <h3>{descriptor.label}</h3>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            <Icon name="close" size={18} />
          </button>
        </header>

        <div className="provider-config-modal-body">
          <section className="provider-config-section">
            <div className="provider-config-row">
              <label>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                <span>Activo</span>
              </label>
              <span className="provider-config-hint">
                {enabled ? 'El provider se incluirá en el catálogo activo' : 'Configurado pero no disponible'}
              </span>
            </div>
          </section>

          {/* auth_none_local */}
          {descriptor.auth_kind === 'auth_none_local' && (
            <section className="provider-config-section">
              <label className="provider-config-field">
                <span>URL base</span>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                />
                <small>Sin autenticación. Solo loopback recomendado.</small>
              </label>
              {showLoopbackWarning && (
                <div className="provider-config-warning">
                  <strong>Advertencia:</strong> la URL no es loopback. Para uso en red deberías añadir un proxy o token.
                </div>
              )}
            </section>
          )}

          {/* auth_api_key / auth_api_key_scoped */}
          {(descriptor.auth_kind === 'auth_api_key' || descriptor.auth_kind === 'auth_api_key_scoped') && (
            <section className="provider-config-section">
              <label className="provider-config-field">
                <span>URL base</span>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={descriptor.base_url || ''}
                />
              </label>
              <label className="provider-config-field">
                <span>API key</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  autoComplete="off"
                />
                <small>Se guarda en el backend. Nunca en el bundle del frontend.</small>
                {initial?.has_secret && !apiKey && <small>Ya existe una credencial cifrada. Déjalo vacío para conservarla.</small>}
              </label>
              <label className="provider-config-field">
                <span>Modelo por defecto (opcional)</span>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="se autodetecta si lo dejas vacío"
                />
              </label>
            </section>
          )}

          {/* auth_oauth_browser */}
          {showOAuthPending && (
            <section className="provider-config-section">
              <div className="provider-config-info">
                <strong>OAuth pendiente (Fase B)</strong>
                <p>La integración completa con navegador y callback se implementa en la siguiente fase. Por ahora puedes preparar los datos:</p>
                <label className="provider-config-field">
                  <span>URL base</span>
                  <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </label>
                <small>Cada usuario registra su propia OAuth App (client_id + client_secret). BAGO no comparte credenciales entre usuarios.</small>
              </div>
            </section>
          )}

          {/* auth_iam_cloud / auth_wif_workload */}
          {showIamPending && (
            <section className="provider-config-section">
              <div className="provider-config-info">
                <strong>Credenciales enterprise (Fase B)</strong>
                <p>Esta fase persiste los metadatos; las credenciales cloud reales llegan en Fase B (keyring del SO).</p>
                <label className="provider-config-field">
                  <span>URL base</span>
                  <input type="text" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                </label>
                <label className="provider-config-field">
                  <span>Referencia a credenciales</span>
                  <input
                    type="text"
                    value={credentialsRef}
                    onChange={(e) => setCredentialsRef(e.target.value)}
                    placeholder="bago://secrets/providers/{id}/default"
                  />
                </label>
              </div>
            </section>
          )}

          {/* auth_device_flow */}
          {showDeviceFlowPending && (
            <section className="provider-config-section">
              <div className="provider-config-info">
                <strong>Device flow (Fase B)</strong>
                <p>Aquí irá el input del código de dispositivo y el botón para iniciar el flujo.</p>
              </div>
            </section>
          )}

          {/* auth_delegated_runtime */}
          {descriptor.auth_kind === 'auth_delegated_runtime' && (
            <section className="provider-config-section">
              <div className="provider-config-info">
                <strong>Runtime delegado</strong>
                <p>BAGO delega en {descriptor.provider_id === 'codex' ? 'el Codex CLI' : 'el Copilot CLI'} ya autenticado por ti.</p>
                {cliInstalled === null ? (
                  <span>Detectando CLI…</span>
                ) : cliInstalled ? (
                  <div className="provider-config-cli-ok">
                    <Icon name="check" size={14} />
                    <span>Detectado: <code>{cliPath}</code></span>
                  </div>
                ) : (
                  <div className="provider-config-cli-missing">
                    <Icon name="warning" size={14} />
                    <span>No se encontró el CLI en el sistema.</span>
                    {cliHint && <small>{cliHint}</small>}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* auth_openai_compat */}
          {showOpenAICompat && (
            <section className="provider-config-section">
              <label className="provider-config-field">
                <span>URL base</span>
                <input
                  type="text"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://mi-servidor.example.com/v1"
                />
              </label>
              <label className="provider-config-field">
                <span>API key (opcional)</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="si el servidor lo requiere"
                  autoComplete="off"
                />
              </label>
              <label className="provider-config-field">
                <span>Modelo por defecto (opcional)</span>
                <input
                  type="text"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="se autodetecta si lo dejas vacío"
                />
              </label>
            </section>
          )}

          {/* Notas del descriptor */}
          {descriptor.notes && descriptor.notes.length > 0 && (
            <section className="provider-config-section provider-config-notes">
              <ul>
                {descriptor.notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </section>
          )}

          <section className="provider-config-section provider-config-models">
            <div className="provider-config-models-head">
              <strong>Modelos del proveedor</strong>
              <div className="provider-config-models-actions">
                <button
                  type="button"
                  className="secondary-button compact"
                  onClick={() => void loadModels()}
                  disabled={modelsLoading}
                >
                  {modelsLoading ? 'Actualizando…' : 'Actualizar catálogo'}
                </button>
                {availableModels.length > 0 && (
                  <button
                    type="button"
                    className="primary-button compact"
                    onClick={() => void saveActiveModels()}
                    disabled={savingModels}
                  >
                    {savingModels ? 'Guardando…' : 'Guardar selección'}
                  </button>
                )}
              </div>
            </div>
            {availableModels.length > 0 && (
              <small className="provider-config-models-hint">
                {availableModels.length} modelos desde {discoverySource}. Marca los que quieras usar.
              </small>
            )}
            {availableModels.length === 0 && !modelsLoading && !modelsError && (
              <small className="provider-config-models-hint">
                El backend no ha devuelto modelos para este proveedor.
              </small>
            )}
            {modelsError && (
              <div className="provider-config-error">
                <Icon name="warning" size={14} />
                <span>{modelsError}</span>
              </div>
            )}
            {availableModels.length > 0 && (
              <ul className="provider-config-models-list">
                {availableModels.map((m) => (
                  <li key={m}>
                    <label>
                      <input
                        type="checkbox"
                        checked={activeModels.has(m)}
                        onChange={() => toggleModel(m)}
                      />
                      <span>{m}</span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
            {activeModels.size > 0 && (
              <small className="provider-config-models-summary">
                {activeModels.size} modelo{activeModels.size === 1 ? '' : 's'} marcado{activeModels.size === 1 ? '' : 's'} como activo
              </small>
            )}
          </section>

          {error && (
            <div className="provider-config-error">
              <Icon name="warning" size={14} />
              <span>{error}</span>
            </div>
          )}
          {saved && (
            <div className="provider-config-success" role="status">
              <Icon name="check" size={14} />
              <span>Registro guardado y catálogo actualizado.</span>
            </div>
          )}
        </div>

        <footer className="provider-config-modal-foot">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={save}
            disabled={saving || (descriptor.auth_kind === 'auth_delegated_runtime' && cliInstalled === false)}
          >
            {saving ? 'Guardando…' : 'Guardar y actualizar modelos'}
          </button>
        </footer>
      </div>
    </div>
  );
}
