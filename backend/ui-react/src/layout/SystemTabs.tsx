import { useEffect, useMemo, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { BagoClient, createBagoClient } from '@/api/client';
import { Icon, type IconName } from '@/shared/Icon';
import { PROVIDER_CATALOG, findProvider } from '@/shared/provider-catalog';
import { ProviderDescriptor } from '@/shared/provider-config';
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
  const [subagents, setSubagents] = useState<Record<string, unknown> | null>(null);
  const [interpret, setInterpret] = useState<{ rules: Record<string, unknown> | null; history: Record<string, unknown> | null }>({ rules: null, history: null });
  const [routes, setRoutes] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [configModal, setConfigModal] = useState<ProviderDescriptor | null>(null);
  const [configInitial, setConfigInitial] = useState<{ enabled?: boolean; base_url?: string; api_key?: string; default_model?: string } | undefined>(undefined);

  function openConfigModal(descriptor: ProviderDescriptor) {
    const state = props.providers.find((p) => String(p.name || p.id) === descriptor.provider_id);
    setConfigInitial(state
      ? {
          enabled: state.enabled !== false,
          base_url: state.base_url ? String(state.base_url) : undefined,
          api_key: undefined, // nunca re-llenar la clave; pedir siempre
          default_model: state.model ? String(state.model) : undefined
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
    [`configured: ${props.providers.filter((provider) => provider.enabled !== false).length}`],
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
              <span>Catálogo BAGO. Click en "Configurar" para registrar un proveedor. Las credenciales nunca viven en el bundle del frontend.</span>
              <ActionMenuButton selection={providersSelection} onInspectSelection={props.onInspectSelection} label="Acciones de proveedores" />
            </div>
            <ul className="provider-list">
              {PROVIDER_CATALOG.map((descriptor) => {
                const state = props.providers.find(
                  (p) => String(p.name || p.id) === descriptor.provider_id
                );
                const enabled = state ? (state.enabled !== false) : descriptor.enabled;
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
                      <span className={`provider-status ${enabled ? 'is-on' : 'is-off'}`}>
                        {enabled ? 'activo' : 'inactivo'}
                      </span>
                    </div>
                    <div className="provider-list-meta">
                      <span>{descriptor.protocol.replace('protocol_', '')}</span>
                      <span> · </span>
                      <span>{descriptor.auth_kind.replace('auth_', '')}</span>
                    </div>
                    {descriptor.base_url && (
                      <div className="provider-list-meta">{descriptor.base_url}</div>
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
          </section>
        )}

        {configModal && (
          <ProviderConfigModal
            descriptor={configModal}
            apiBase={props.apiBase}
            initial={configInitial}
            onClose={() => setConfigModal(null)}
            onSave={async (cfg) => {
              await props.onConfigureProvider(configModal.provider_id, cfg);
            }}
            onDetectCli={async (tool) => {
              const res = await fetch(`${props.apiBase}/providers/cli-detect?tool=${tool}`);
              if (!res.ok) throw new Error('No se pudo detectar el CLI');
              return res.json();
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
            <p className="system-tab-description">Refuerzo de aprendizaje en modo observador. No toma decisiones automáticamente.</p>
            {!rl ? <LoadingState label="RL" /> : (
              <div className="rl-stack">
                <DataBlock label="Estado" value={String(rlStatus.enabled ? 'ON' : 'OFF')} hint={String(rlStatus.mode || '?')} />
                <DataBlock label="Autoridad" value={String(rlStatus.authority || '?')} />
                <DataBlock label="Eventos" value={String(rlStatus.events_logged ?? '?')} />
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
