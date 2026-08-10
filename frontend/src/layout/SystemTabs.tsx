import { useCallback, useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { BagoClient, createBagoClient } from '@/api/client';
import { Icon, type IconName } from '@/shared/Icon';
import { resolveProviderDescriptor } from '@/shared/provider-catalog';
import { ProviderDescriptor } from '@/shared/provider-config';
import { normalizeProviderModels } from '@/shared/providerModels';
import { ProviderConfigModal } from './ProviderConfigModal';
import type { ContextTargetKind, SelectionRecord } from '@/contracts/backend';
type TabId = 'overview' | 'router' | 'providers' | 'audit' | 'simulation' | 'rl' | 'subagents' | 'interpret' | 'routes';

interface Tab {
  id: TabId;
  label: string;
  icon: IconName;
  experimental?: boolean;
}

const TABS: Tab[] = [
  { id: 'overview', label: 'Resumen', icon: 'system' },
  { id: 'router', label: 'Router', icon: 'model' },
  { id: 'providers', label: 'Proveedores', icon: 'server' },
  { id: 'audit', label: 'Auditoría', icon: 'inspector' },
  { id: 'simulation', label: 'Simulación', icon: 'pipeline' },
  { id: 'rl', label: 'RL', icon: 'live', experimental: true },
  { id: 'subagents', label: 'Subagentes', icon: 'node' },
  { id: 'interpret', label: 'Interpret', icon: 'command' },
  { id: 'routes', label: 'Rutas API', icon: 'actions' }
];

interface Props {
  apiBase: string;
  apiToken: string;
  routerEntries: Array<Record<string, unknown>>;
  routerAuto: boolean;
  routerSelectedCount: number;
  routerLastPick: string;
  onRefreshRouter: () => Promise<void>;
  onToggleRouter: (key: string) => Promise<void>;
  onSetRouterAuto: (enabled: boolean) => Promise<void>;
  onConfigureProvider: (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }) => Promise<void>;
  providers: Array<Record<string, unknown>>;
  onInspectSelection?: (selection: SelectionRecord, position?: { x: number; y: number }) => void;
}

function DataBlock({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="system-data-block">
      <span className="system-data-label">{label}</span>
      <strong>{value}</strong>
      {hint && <span className="system-data-hint">{hint}</span>}
    </div>
  );
}

function LoadingState({ label }: { label: string }) {
  return <div className="system-tab-loading">Cargando {label}…</div>;
}

function ErrorState({ error }: { error: string }) {
  return <div className="system-tab-error">⚠ {error}</div>;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function JsonView({ data }: { data: unknown }) {
  const text = (() => {
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  })();
  return <pre className="system-json">{text}</pre>;
}

function systemSelection(id: string, kind: string, title: string, summary: string, detail: string[], raw: unknown, targetKind?: ContextTargetKind): SelectionRecord {
  return { id, kind, targetKind, title, summary, detail, raw };
}


function ActionMenuButton({ selection, onInspectSelection, label = 'Acciones' }: { selection: SelectionRecord; onInspectSelection?: (selection: SelectionRecord, position?: { x: number; y: number }) => void; label?: string }) {
  if (!onInspectSelection) return null;
  return (
    <button
      type="button"
      className="icon-button context-action-button"
      title={label}
      aria-label={label}
      aria-haspopup="menu"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        onInspectSelection(selection, { x: rect.left, y: rect.bottom + 6 });
      }}
    >
      <Icon name="more" size={14} />
    </button>
  );
}

function openContextMenu(
  event: ReactMouseEvent<HTMLElement>,
  selection: SelectionRecord,
  onInspectSelection?: (selection: SelectionRecord, position?: { x: number; y: number }) => void
) {
  if (!onInspectSelection) return;
  event.preventDefault();
  event.stopPropagation();
  onInspectSelection(selection, { x: event.clientX, y: event.clientY });
}

export function SystemTabs(props: Props) {
  const client = useMemo(() => createBagoClient(props.apiBase, props.apiToken), [props.apiBase, props.apiToken]);
  const [active, setActive] = useState<TabId>('overview');
  const [audit, setAudit] = useState<Record<string, unknown> | null>(null);
  const [simulation, setSimulation] = useState<Record<string, unknown> | null>(null);
  const [rl, setRl] = useState<Record<string, unknown> | null>(null);
  const [rlBusy, setRlBusy] = useState<string>('');
  const [rlResult, setRlResult] = useState<Record<string, unknown> | null>(null);
  const [subagents, setSubagents] = useState<Record<string, unknown> | null>(null);
  const [interpret, setInterpret] = useState<{ rules: Record<string, unknown> | null; history: Record<string, unknown> | null }>({ rules: null, history: null });
  const [routes, setRoutes] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [configModal, setConfigModal] = useState<ProviderDescriptor | null>(null);
  const [providerContracts, setProviderContracts] = useState<Record<string, unknown> | null>(null);
  const [providerContractsBusy, setProviderContractsBusy] = useState(false);
  const [configInitial, setConfigInitial] = useState<{
    enabled?: boolean;
    base_url?: string;
    api_key?: string;
    default_model?: string;
    has_secret?: boolean;
    models?: string[];
  } | undefined>(undefined);

  function openConfigModal(descriptor: ProviderDescriptor) {
    const state = props.providers.find((p) => String(p.name || p.id) === descriptor.provider_id);
    setConfigInitial(state
      ? {
          enabled: state.enabled === true,
          base_url: state.base_url ? String(state.base_url) : undefined,
          api_key: undefined, // nunca re-llenar la clave; pedir siempre
          default_model: state.default_model ? String(state.default_model) : undefined,
          has_secret: Boolean(state.has_secret),
          models: normalizeProviderModels({ models: state.models }).map((entry) => entry.id)
        }
      : undefined);
    setConfigModal(descriptor);
  }

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const load = async () => {
      try {
        if (active === 'audit') {
          const [proj, bago, ledger] = await Promise.all([
            client.getAuditProject().catch((e) => ({ error: String(e) })),
            client.getAuditBago().catch((e) => ({ error: String(e) })),
            client.getAuditLedger().catch((e) => ({ error: String(e) }))
          ]);
          if (!cancelled) setAudit({ project: proj, bago, ledger });
        } else if (active === 'simulation') {
          const [status, events] = await Promise.all([
            client.getSimulationStatus().catch((e) => ({ error: String(e) })),
            client.getSimulationEvents().catch((e) => ({ error: String(e) }))
          ]);
          if (!cancelled) setSimulation({ status, events });
        } else if (active === 'rl') {
          const status = await client.getRlStatus().catch((e) => ({ error: String(e) }));
          if (!cancelled) setRl(status);
        } else if (active === 'subagents') {
          const cat = await client.getSubagentsCatalogue().catch((e) => ({ error: String(e) }));
          if (!cancelled) setSubagents(cat);
        } else if (active === 'interpret') {
          const [rules, history] = await Promise.all([
            client.getInterpretRules().catch((e) => ({ error: String(e) })),
            client.getInterpretHistory().catch((e) => ({ error: String(e) }))
          ]);
          if (!cancelled) setInterpret({ rules, history });
        } else if (active === 'routes') {
          const r = await client.getRoutesFresh().catch((e) => ({ error: String(e) }));
          if (!cancelled) setRoutes(r as Record<string, unknown>);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    };
    if (active !== 'overview' && active !== 'router' && active !== 'providers') {
      void load();
    }
    return () => { cancelled = true; };
  }, [active, client]);

  const simulationStatus = asRecord(simulation?.status);
  const rlStatus = asRecord(rl);

  async function runRlAction(action: 'refresh' | 'shadow' | 'train' | 'eval') {
    setRlBusy(action);
    setError(null);
    try {
      const result = action === 'refresh'
        ? await client.getRlStatus()
        : action === 'shadow'
          ? await client.setRlShadow({ enabled: !Boolean(rlStatus.enabled) })
          : action === 'train'
            ? await client.trainRlBc()
            : await client.evalRlPolicy();
      if (action === 'refresh' || action === 'shadow') setRl(result);
      setRlResult(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setRlBusy('');
    }
  }
  const overviewSelection = systemSelection(
    'system-overview',
    'system-overview',
    'Estado del backend',
    `${props.routerSelectedCount} modelos activos · router ${props.routerAuto ? 'auto' : 'manual'}`,
    [`last_pick: ${props.routerLastPick || '—'}`, `providers: ${props.providers.length}`],
    { routerAuto: props.routerAuto, routerSelectedCount: props.routerSelectedCount, providers: props.providers },
    'system.surface'
  );
  const routerSelection = systemSelection(
    'system-router',
    'system-router',
    'Router',
    `${props.routerSelectedCount} seleccionados · ${props.routerAuto ? 'auto' : 'manual'}`,
    [`last_pick: ${props.routerLastPick || '—'}`],
    { entries: props.routerEntries, routerAuto: props.routerAuto },
    'system.router'
  );
  const providersSelection = systemSelection(
    'system-providers',
    'system-providers',
    'Proveedores',
    `${props.providers.length} proveedores`,
    [`configured: ${props.providers.filter((provider) => provider.configured === true).length}`],
    props.providers,
    'system.provider'
  );

  return (
    <div className="system-tabs">
      <div className="system-tabs-rail" role="tablist" aria-label="Secciones del sistema">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            className={`system-tab-button ${active === tab.id ? 'is-active' : ''}`}
            onClick={() => setActive(tab.id)}
            onContextMenu={(event) => openContextMenu(event, systemSelection(
              `system-tab-${tab.id}`,
              'system-tab',
              tab.label,
              tab.experimental ? 'Pestaña experimental del sistema' : 'Pestaña del sistema',
              [`tab: ${tab.id}`, `active: ${String(active === tab.id)}`],
              tab,
              'system.surface'
            ), props.onInspectSelection)}
          >
            <Icon name={tab.icon} size={14} />
            <span>{tab.label}</span>
            {tab.experimental && <span className="system-tab-experimental" title="Experimental">·</span>}
          </button>
        ))}
      </div>

      <div className="system-tabs-content">
        {active === 'overview' && (
          <section
            className="system-tab-panel"
            role="tabpanel"
            onContextMenu={(event) => openContextMenu(event, overviewSelection, props.onInspectSelection)}
          >
            <h3>Estado del backend</h3>
            <p className="system-tab-description">Visión rápida del router, los providers y el modo de operación.</p>
            <div className="system-data-grid">
              <DataBlock label="Router auto" value={props.routerAuto ? 'ON' : 'OFF'} hint="Cambia entre modelos según necesidad" />
              <DataBlock label="Seleccionados" value={props.routerSelectedCount} hint="Modelos activos en el router" />
              <DataBlock label="Última elección" value={props.routerLastPick || '—'} />
              <DataBlock label="Proveedores" value={props.providers.length} hint="Disponibles en el catálogo" />
            </div>
            <button className="secondary-button compact" type="button" onClick={() => void props.onRefreshRouter()}>
              <Icon name="refresh" size={14} /> Refrescar router
            </button>
            <ActionMenuButton selection={overviewSelection} onInspectSelection={props.onInspectSelection} label="Acciones de sistema" />
            <ReleaseUpdateCard client={client} />
          </section>
        )}

        {active === 'router' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Router</h3>
            <p className="system-tab-description">Modelos descubiertos y selección activa.</p>
            <div className="router-toolbar">
              <ActionMenuButton selection={routerSelection} onInspectSelection={props.onInspectSelection} label="Acciones del router" />
              <label className="router-toggle">
                <input
                  type="checkbox"
                  checked={props.routerAuto}
                  onChange={(e) => void props.onSetRouterAuto(e.target.checked)}
                />
                <span>Auto-switch entre modelos</span>
              </label>
            </div>
            {props.routerEntries.length === 0 ? (
              <ErrorState error="No hay modelos en el router" />
            ) : (
              <ul className="router-list">
                {props.routerEntries.map((entry, idx) => {
                  const key = String(entry.key || `${entry.provider}/${entry.model_id}` || `entry-${idx}`);
                  const isSelected = Boolean(entry.selected);
                  return (
                    <li
                      key={key}
                      className={`router-list-item ${isSelected ? 'is-selected' : ''}`}
                      onContextMenu={(event) => openContextMenu(event, systemSelection(
                        key,
                        'router-entry',
                        String(entry.model_id || entry.wire_name || key),
                        String(entry.best_for || entry.provider || 'Modelo de router'),
                        [
                          `provider: ${String(entry.provider || 'unknown')}`,
                          `selected: ${String(isSelected)}`,
                          `context_tokens: ${String(entry.context_tokens || 'unknown')}`
                        ],
                        entry,
                        'system.router'
                      ), props.onInspectSelection)}
                    >
                      <button
                        type="button"
                        className="router-list-toggle"
                        onClick={() => void props.onToggleRouter(key)}
                        title={isSelected ? 'Quitar del router' : 'Añadir al router'}
                      >
                        <span className={`router-list-dot ${isSelected ? 'is-on' : 'is-off'}`} />
                        <span className="router-list-name">
                          {String(entry.provider || '?')} · {String(entry.model_id || entry.wire_name || '?')}
                        </span>
                        {Boolean(entry.context_tokens) && (
                          <span className="router-list-meta">{String(entry.context_tokens)} ctx</span>
                        )}
                        {Boolean(entry.best_for) && (
                          <span className="router-list-tag">{String(entry.best_for)}</span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        )}

        {active === 'providers' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Proveedores</h3>
            <div className="system-tab-description with-actions">
              <span>Registro activo del backend. Configura cada adaptador real y consulta su catálogo canónico de modelos.</span>
              <ActionMenuButton selection={providersSelection} onInspectSelection={props.onInspectSelection} label="Acciones de proveedores" />
            </div>
            <div className="provider-contracts">
              <button
                type="button"
                className="secondary-button compact"
                disabled={providerContractsBusy}
                onClick={() => {
                  setProviderContractsBusy(true);
                  setError(null);
                  void client.verifyProviderContracts()
                    .then(setProviderContracts)
                    .catch((e) => setError(String(e)))
                    .finally(() => setProviderContractsBusy(false));
                }}
              >
                {providerContractsBusy ? 'Verificando…' : 'Verificar 6 contratos cloud'}
              </button>
              {providerContracts && (
                <span className={`provider-status ${providerContracts.ok ? 'is-on' : 'is-off'}`}>
                  {String(providerContracts.passed ?? 0)}/{String(providerContracts.expected ?? 6)} offline · sin tráfico
                </span>
              )}
            </div>
            {error && <ErrorState error={error} />}
            {props.providers.length === 0 ? (
              <ErrorState error="El backend no ha devuelto proveedores registrados" />
            ) : (
            <ul className="provider-list">
              {props.providers.map((state) => {
                const providerId = String(state.id || state.name || '').trim();
                const descriptor = resolveProviderDescriptor(providerId, String(state.label || state.name || providerId));
                const enabled = state.enabled === true;
                const configured = state.configured === true;
                const models = normalizeProviderModels({ models: state.models }).map((entry) => entry.id);
                const statusLabel = !enabled ? 'inactivo' : configured ? 'listo' : 'pendiente';
                return (
                  <li
                    key={descriptor.provider_id}
                    className="provider-list-item"
                    onContextMenu={(event) => openContextMenu(event, systemSelection(
                      descriptor.provider_id,
                      'provider',
                      descriptor.label,
                      descriptor.notes?.join(' · ') || descriptor.protocol,
                      [
                        `protocol: ${descriptor.protocol}`,
                        `auth: ${descriptor.auth_kind}`,
                        `enabled: ${String(enabled)}`
                      ],
                      { descriptor, state },
                      'system.provider'
                    ), props.onInspectSelection)}
                  >
                    <div className="provider-list-head">
                      <strong>{descriptor.label}</strong>
                      <span className={`provider-status ${enabled && configured ? 'is-on' : 'is-off'}`}>
                        {statusLabel}
                      </span>
                    </div>
                    <div className="provider-list-meta">
                      <span>{descriptor.protocol.replace('protocol_', '')}</span>
                      <span> · </span>
                      <span>{descriptor.auth_kind.replace('auth_', '')}</span>
                    </div>
                    <div className="provider-list-meta">
                      {models.length} modelo{models.length === 1 ? '' : 's'} · fuente: {String(state.models_source || 'backend')}
                    </div>
                    {models.length > 0 && (
                      <div className="provider-list-models" aria-label={`Modelos reales de ${descriptor.label}`}>
                        {models.slice(0, 4).map((modelId) => <code key={modelId}>{modelId}</code>)}
                        {models.length > 4 && <span>+{models.length - 4}</span>}
                      </div>
                    )}
                    <button
                      type="button"
                      className="secondary-button compact"
                      onClick={() => openConfigModal(descriptor)}
                    >
                      Configurar
                    </button>
                  </li>
                );
              })}
            </ul>
            )}
          </section>
        )}

        {configModal && (
          <ProviderConfigModal
            descriptor={configModal}
            client={client}
            initial={configInitial}
            onClose={() => setConfigModal(null)}
            onSave={async (cfg) => {
              await props.onConfigureProvider(configModal.provider_id, cfg);
            }}
            onDetectCli={async (tool) => {
              return client.detectProviderCli(tool);
            }}
          />
        )}

        {active === 'audit' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Auditoría</h3>
            <p className="system-tab-description">Eventos de auditoría del proyecto y del framework.</p>
            {error && <ErrorState error={error} />}
            {!audit ? <LoadingState label="auditoría" /> : (
              <div className="audit-stack">
                <details open>
                  <summary>Proyecto</summary>
                  <JsonView data={audit.project} />
                </details>
                <details>
                  <summary>BAGO framework</summary>
                  <JsonView data={audit.bago} />
                </details>
                <details>
                  <summary>Ledger completo</summary>
                  <JsonView data={audit.ledger} />
                </details>
              </div>
            )}
          </section>
        )}

        {active === 'simulation' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Simulación</h3>
            <p className="system-tab-description">Estado y eventos de la simulación shadow (observer-only).</p>
            {!simulation ? <LoadingState label="simulación" /> : (
              <div className="simulation-stack">
                <DataBlock label="Estado" value={String(simulationStatus.enabled ? 'ON' : 'OFF')} hint={String(simulationStatus.mode || '?')} />
                <DataBlock label="Autoridad" value={String(simulationStatus.authority || '?')} hint={String(simulationStatus.mode_note || '').slice(0, 60)} />
                <DataBlock label="Eventos registrados" value={String(simulationStatus.events_logged ?? '?')} />
                <details>
                  <summary>Eventos</summary>
                  <JsonView data={simulation.events} />
                </details>
              </div>
            )}
          </section>
        )}

        {active === 'rl' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>RL <span className="system-tab-badge-experimental">experimental</span></h3>
            <p className="system-tab-description">Entrena, evalúa y registra recomendaciones. La autoridad permanece en observer-only: nunca ejecuta acciones.</p>
            {error && <ErrorState error={error} />}
            {!rl ? <LoadingState label="RL" /> : (
              <div className="rl-stack">
                <DataBlock label="Estado" value={String(rlStatus.enabled ? 'ON' : 'OFF')} hint={String(rlStatus.mode || '?')} />
                <DataBlock label="Autoridad" value={String(rlStatus.authority || '?')} />
                <DataBlock label="Eventos" value={String(rlStatus.events_logged ?? '?')} />
                <DataBlock label="Puede ejecutar" value={rlStatus.can_execute === true ? 'SÍ' : 'NO'} hint="Bloqueo de seguridad permanente" />
                <div className="rl-actions" aria-label="Controles RL">
                  <button className="secondary-button compact" type="button" disabled={Boolean(rlBusy)} onClick={() => void runRlAction('refresh')}>Actualizar</button>
                  <button className="secondary-button compact" type="button" disabled={Boolean(rlBusy)} onClick={() => void runRlAction('shadow')}>{rlStatus.enabled ? 'Desactivar shadow' : 'Activar shadow'}</button>
                  <button className="primary-button compact" type="button" disabled={Boolean(rlBusy)} onClick={() => void runRlAction('train')}>Entrenar BC</button>
                  <button className="secondary-button compact" type="button" disabled={Boolean(rlBusy)} onClick={() => void runRlAction('eval')}>Evaluar política</button>
                </div>
                {rlBusy && <div className="system-tab-meta">Ejecutando {rlBusy}…</div>}
                {rlResult && <details open><summary>Resultado de la última acción</summary><JsonView data={rlResult} /></details>}
                {Boolean(rlStatus.log_path) && <div className="system-tab-meta">Log: {String(rlStatus.log_path)}</div>}
                <details>
                  <summary>Detalle completo</summary>
                  <JsonView data={rl} />
                </details>
              </div>
            )}
          </section>
        )}

        {active === 'subagents' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Subagentes</h3>
            <p className="system-tab-description">Catálogo de subagentes disponibles para el pipeline.</p>
            {!subagents ? <LoadingState label="subagentes" /> : (
              subagents.error
                ? <ErrorState error={String(subagents.error)} />
                : <JsonView data={subagents} />
            )}
          </section>
        )}

        {active === 'interpret' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Interpret</h3>
            <p className="system-tab-description">Reglas de interpretación e historial de invocaciones.</p>
            {!interpret.rules && !interpret.history ? <LoadingState label="interpret" /> : (
              <div className="interpret-stack">
                <details open>
                  <summary>Reglas</summary>
                  <JsonView data={interpret.rules} />
                </details>
                <details>
                  <summary>Historial</summary>
                  <JsonView data={interpret.history} />
                </details>
              </div>
            )}
          </section>
        )}

        {active === 'routes' && (
          <section className="system-tab-panel" role="tabpanel">
            <h3>Rutas API</h3>
            <p className="system-tab-description">Mapa vivo de las rutas HTTP expuestas por el bridge.</p>
            {!routes ? <LoadingState label="rutas" /> : (
              <RoutesView routes={routes} />
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function ReleaseUpdateCard({ client }: { client: BagoClient }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [updateState, setUpdateState] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const refresh = useCallback(async () => {
    setBusy(true);
    try {
      const checked = await client.checkReleaseUpdate();
      setData(checked);
      setUpdateState(await client.getReleaseUpdateStatus());
      setMessage(String(checked.warning || ''));
    }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }, [client]);

  useEffect(() => { void refresh(); }, [refresh]);

  const stateName = String(updateState?.status || 'idle');
  useEffect(() => {
    if (!['queued', 'downloading', 'verifying', 'applying'].includes(stateName)) return;
    const timer = window.setInterval(() => {
      void client.getReleaseUpdateStatus()
        .then(setUpdateState)
        .catch((error) => setMessage(error instanceof Error ? error.message : String(error)));
    }, 750);
    return () => window.clearInterval(timer);
  }, [client, stateName]);

  const download = async () => {
    setBusy(true);
    try {
      const result = await client.startReleaseUpdate(String(data?.latest || ''));
      setUpdateState(result);
      setMessage(String(result.message || 'Descarga iniciada.'));
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };

  const apply = async () => {
    if (!window.confirm('BAGO se cerrará y volverá a abrirse al terminar. ¿Instalar la actualización ahora?')) return;
    setBusy(true);
    try {
      const result = await client.applyReleaseUpdate();
      setUpdateState(result);
      setMessage(String(result.message || 'Instalando actualización…'));
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };

  const installation = asRecord(data?.installation || updateState?.installation);
  const canInstall = installation.ready === true;
  const available = Boolean(data?.available || updateState?.available);
  const progress = Math.max(0, Math.min(100, Number(updateState?.percent || 0)));
  const active = ['queued', 'downloading', 'verifying', 'applying'].includes(stateName);
  const ready = stateName === 'ready';
  const completed = stateName === 'completed';
  const statusMessage = message || String(updateState?.message || '');
  const title = completed
    ? 'Actualización completada'
    : available
      ? `Nueva versión ${String(data?.latest || updateState?.latest || '')}`
      : 'BAGO está actualizado';
  const detail = statusMessage || (!canInstall && available
    ? String(installation.reason || 'Esta copia no admite actualización integrada.')
    : `Versión instalada: ${String(data?.current || updateState?.current || '—')}. Se conservan estado, memoria y proyectos.`);

  return <article className="release-update-card">
    <div className="release-update-copy">
      <span className="surface-eyebrow"><Icon name="refresh" size={13} /> Actualización de BAGO</span>
      <strong>{title}</strong>
      <small>{detail}</small>
      {(active || ready) && <div className="release-update-progress" role="progressbar" aria-label="Progreso de actualización" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{ width: `${progress}%` }} /></div>}
      {Boolean(data?.release_url) && <a className="release-update-link" href={String(data?.release_url)} target="_blank" rel="noreferrer">Ver detalles de la release</a>}
    </div>
    <div className="system-panel-actions">
      <button className="text-button" type="button" onClick={() => void refresh()} disabled={busy || active}>Comprobar</button>
      {available && !ready && !active && <button className="primary-button compact" type="button" onClick={() => void download()} disabled={busy || !canInstall}>Descargar y verificar</button>}
      {ready && <button className="primary-button compact" type="button" onClick={() => void apply()} disabled={busy}>Instalar y reiniciar</button>}
    </div>
  </article>;
}

function RoutesView({ routes }: { routes: Record<string, unknown> }) {
  const list = Array.isArray(routes.routes) ? (routes.routes as Array<Record<string, unknown>>) : [];
  return (
    <div className="routes-view">
      <DataBlock label="Total" value={String(routes.count ?? list.length)} />
      <details open>
        <summary>Listado ({list.length})</summary>
        <table className="routes-table">
          <thead>
            <tr>
              <th>Método</th>
              <th>Ruta</th>
              <th>Handler</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r, idx) => (
              <tr key={`${r.method}-${r.path}-${idx}`}>
                <td><span className={`route-method method-${String(r.method || 'GET').toLowerCase()}`}>{String(r.method || '?')}</span></td>
                <td className="route-path">{String(r.path || '?')}</td>
                <td className="route-handler">{String(r.handler_module || '?')}.{String(r.handler_fn || '?')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
