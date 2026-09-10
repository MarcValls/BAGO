import { useCallback, useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import type { AgentConfig, AgentUpdateRequest } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';
import { mergeProviderStates } from '@/shared/providerStates';
import { normalizeProviderModels } from '@/shared/providerModels';
import { SubagentCatalogue } from '@/layout/OperationalTools';
import {
  agentModelSelectionAvailable,
  buildAgentModelGroups,
  decodeAgentModelSelection,
  encodeAgentModelSelection,
  isProviderLoggedInUsable,
  resolveAgentModelSelection,
  type AgentModelGroup,
} from './agentProviderSelection';

interface Props {
  client: BagoClient;
  onClose: () => void;
}

interface AgentCreationDraft {
  name: string;
  systemPrompt: string;
  generatedAt: string;
  sourceText: string;
}

interface ProviderOptionsState {
  groups: AgentModelGroup[];
  loading: boolean;
  error: string | null;
  warning: string | null;
}

interface AgentEditorState {
  agents: AgentConfig[];
  selectedAgent: AgentConfig | null;
  loading: boolean;
  saving: boolean;
  testing: boolean;
  error: string | null;
  savedMessage: string | null;
  testOutput: string | null;
  // form fields
  name: string;
  systemPrompt: string;
  model: string;
  provider: string;
  temperature: number;
  maxTokens: number;
  enabled: boolean;
  isDirty: boolean;
}

function readString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function chatPayloadText(payload: unknown): string {
  if (typeof payload === 'string') return payload;
  const record = readRecord(payload);
  const nested = readRecord(record.data || record.result);
  return readString(record.response)
    || readString(record.text)
    || readString(record.message)
    || readString(record.content)
    || readString(nested.response)
    || readString(nested.text)
    || readString(nested.message);
}

function parseJsonObject(text: string): Record<string, unknown> | null {
  const clean = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();
  if (!clean) return null;
  const start = clean.indexOf('{');
  const end = clean.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try {
    const parsed = JSON.parse(clean.slice(start, end + 1));
    return readRecord(parsed);
  } catch {
    return null;
  }
}

function parseAgentDraft(payload: unknown): AgentCreationDraft {
  const text = chatPayloadText(payload);
  const record = parseJsonObject(text);
  const draft = readRecord(record?.draft || record?.agent || record);
  const name = readString(draft.name || draft.agentName || draft.agent_name || draft.title);
  const systemPrompt = readString(draft.systemPrompt || draft.system_prompt || draft.prompt || draft.instructions);
  if (!name || !systemPrompt) {
    throw new Error('La IA no devolvió un borrador válido con name y systemPrompt.');
  }
  return {
    name,
    systemPrompt,
    generatedAt: new Date().toISOString(),
    sourceText: text,
  };
}

function createDraftPrompt(goal: string, groups: AgentModelGroup[]): string {
  const eligible = groups
    .map((group) => `${group.providerId}: ${group.models.slice(0, 6).join(', ')}`)
    .join('\n');
  return [
    'Genera un borrador de agente configurable para BAGO.',
    'Devuelve SOLO JSON valido, sin markdown ni explicaciones, con esta forma exacta:',
    '{"name":"Nombre corto","systemPrompt":"System prompt completo en espanol"}',
    'El systemPrompt debe ser especifico, operativo, no debe incluir credenciales y debe preservar que el backend de BAGO es la autoridad.',
    `Objetivo del usuario: ${goal || 'crear un agente BAGO general de apoyo operativo'}`,
    eligible ? `Modelos elegibles confirmados por backend para contexto de la propuesta:\n${eligible}` : 'No inventes proveedores ni modelos; el frontend los seleccionara desde el backend.',
  ].join('\n');
}

function providerIdFromRecord(provider: Record<string, unknown>): string {
  return readString(provider.id || provider.name || provider.canonical_id);
}

function ProviderOptionsNotice({ options }: { options: ProviderOptionsState }) {
  if (options.loading) {
    return <div className="agent-provider-notice" role="status">Cargando proveedores confirmados por backend…</div>;
  }
  if (options.error) {
    return <div className="agent-provider-notice is-error" role="alert">{options.error}</div>;
  }
  if (options.warning) {
    return <div className="agent-provider-notice is-warning" role="status">{options.warning}</div>;
  }
  if (options.groups.length === 0) {
    return (
      <div className="agent-provider-notice is-warning" role="status">
        No hay modelos de proveedores configurados, habilitados y usables. Configura un proveedor antes de crear o reasignar agentes.
      </div>
    );
  }
  return <div className="agent-provider-notice" role="status">{options.groups.length} proveedores usables con modelos confirmados.</div>;
}

interface ProviderModelFieldsProps {
  groups: AgentModelGroup[];
  provider: string;
  model: string;
  disabled?: boolean;
  onChange: (provider: string, model: string) => void;
}

function ProviderModelFields({ groups, provider, model, disabled, onChange }: ProviderModelFieldsProps) {
  const resolvedSelection = resolveAgentModelSelection(groups, provider, model);
  const selectedProvider = resolvedSelection?.provider || '';
  const selectedModel = resolvedSelection?.model || '';
  const selectedModelValue = selectedProvider && selectedModel
    ? encodeAgentModelSelection(selectedProvider, selectedModel)
    : '';

  return (
    <div className="agent-form-row">
      <div className="form-group">
        <label htmlFor="agent-provider">Proveedor</label>
        <select
          id="agent-provider"
          value={selectedProvider}
          disabled={disabled || groups.length === 0}
          onChange={(event) => {
            const group = groups.find((entry) => entry.providerId === event.target.value);
            onChange(group?.providerId || '', group?.models[0] || '');
          }}
        >
          <option value="">{groups.length ? 'Selecciona proveedor' : 'Sin proveedores usables'}</option>
          {groups.map((group) => (
            <option key={group.providerId} value={group.providerId}>
              {group.label} ({group.providerId})
            </option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label htmlFor="agent-model">Modelo</label>
        <select
          id="agent-model"
          value={selectedModelValue}
          disabled={disabled || groups.length === 0}
          onChange={(event) => {
            const decoded = decodeAgentModelSelection(event.target.value);
            onChange(decoded?.provider || '', decoded?.model || '');
          }}
        >
          <option value="">{groups.length ? 'Selecciona modelo' : 'Sin modelos usables'}</option>
          {groups.map((group) => (
            <optgroup key={group.providerId} label={`${group.label} · ${group.state}`}>
              {group.models.map((entry) => (
                <option key={`${group.providerId}:${entry}`} value={encodeAgentModelSelection(group.providerId, entry)}>
                  {entry}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
    </div>
  );
}

export function AgentEditorPanel({ client, onClose }: Props) {
  const [canonicalCatalogue, setCanonicalCatalogue] = useState<Record<string, unknown> | null>(null);
  const [canonicalError, setCanonicalError] = useState<string | null>(null);
  const [canonicalLoading, setCanonicalLoading] = useState(true);
  const [providerOptions, setProviderOptions] = useState<ProviderOptionsState>({
    groups: [],
    loading: true,
    error: null,
    warning: null,
  });
  const [creationGoal, setCreationGoal] = useState('');
  const [creationDraft, setCreationDraft] = useState<AgentCreationDraft | null>(null);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [state, setState] = useState<AgentEditorState>({
    agents: [],
    selectedAgent: null,
    loading: true,
    saving: false,
    testing: false,
    error: null,
    savedMessage: null,
    testOutput: null,
    name: '',
    systemPrompt: '',
    model: '',
    provider: '',
    temperature: 0.7,
    maxTokens: 4096,
    enabled: true,
    isDirty: false,
  });

  const loadAgents = useCallback(async () => {
    try {
      const data = await client.listAgents();
      setState((s) => ({ ...s, agents: data.agents, loading: false, error: null }));
    } catch (e) {
      setState((s) => ({ ...s, loading: false, error: friendlyErrorMessage(e) }));
    }
  }, [client]);

  const loadProviderOptions = useCallback(async () => {
    setProviderOptions((current) => ({ ...current, loading: true, error: null, warning: null }));
    try {
      const data = await client.getProviders();
      const merged = mergeProviderStates(data);
      const eligible = merged.filter(isProviderLoggedInUsable);
      const extraModels: Record<string, string[]> = {};
      const warnings: string[] = [];

      await Promise.all(eligible.map(async (provider) => {
        const providerId = providerIdFromRecord(provider);
        if (!providerId) return;
        const collected: string[] = [];
        try {
          const modelsPayload = await client.getModels(providerId);
          if (modelsPayload.ok === false) {
            warnings.push(`${providerId}: ${String(modelsPayload.error || 'catálogo no disponible')}`);
          } else {
            collected.push(...normalizeProviderModels(modelsPayload).filter((entry) => entry.available).map((entry) => entry.id));
          }
        } catch (error) {
          warnings.push(`${providerId}: ${friendlyErrorMessage(error, 'no se pudo cargar el catálogo')}`);
        }

        try {
          const activePayload = await client.getActiveProviderModels(providerId);
          if (Array.isArray(activePayload.active_models)) {
            collected.push(...activePayload.active_models.map(String).filter(Boolean));
          }
        } catch (error) {
          warnings.push(`${providerId}: ${friendlyErrorMessage(error, 'no se pudo cargar la selección activa')}`);
        }
        extraModels[providerId] = collected;
      }));

      setProviderOptions({
        groups: buildAgentModelGroups(merged, extraModels),
        loading: false,
        error: null,
        warning: warnings.length ? `Algunos catálogos no se pudieron refrescar; se usan modelos ya confirmados. ${warnings.slice(0, 2).join(' · ')}` : null,
      });
    } catch (e) {
      setProviderOptions({
        groups: [],
        loading: false,
        error: friendlyErrorMessage(e, 'No se pudieron cargar los proveedores del backend'),
        warning: null,
      });
    }
  }, [client]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    loadProviderOptions();
  }, [loadProviderOptions]);

  useEffect(() => {
    let cancelled = false;
    client.getSubagentsCatalogue()
      .then((catalogue) => { if (!cancelled) setCanonicalCatalogue(catalogue); })
      .catch((error: unknown) => { if (!cancelled) setCanonicalError(friendlyErrorMessage(error)); })
      .finally(() => { if (!cancelled) setCanonicalLoading(false); });
    return () => { cancelled = true; };
  }, [client]);

  const canonicalCount = Array.isArray(canonicalCatalogue?.agents) ? canonicalCatalogue.agents.length : 0;
  const currentSelectionUnavailable = useMemo(() => Boolean(
    !providerOptions.loading
    && (state.provider || state.model)
    && !agentModelSelectionAvailable(providerOptions.groups, state.provider, state.model)
  ), [providerOptions.groups, providerOptions.loading, state.model, state.provider]);
  const agentModelSelectionChanged = Boolean(state.selectedAgent && (
    state.provider !== (state.selectedAgent.provider || '')
    || state.model !== (state.selectedAgent.model || '')
  ));

  const canCreateDraft = Boolean(creationDraft && state.name.trim() && state.systemPrompt.trim())
    && agentModelSelectionAvailable(providerOptions.groups, state.provider, state.model);

  const selectAgent = useCallback((agent: AgentConfig) => {
    const resolved = resolveAgentModelSelection(providerOptions.groups, agent.provider, agent.model);
    setCreationDraft(null);
    setDraftError(null);
    setConfirmDelete(false);
    setState((s) => ({
      ...s,
      selectedAgent: agent,
      name: agent.name,
      systemPrompt: agent.systemPrompt,
      model: resolved?.model || '',
      provider: resolved?.provider || '',
      temperature: agent.temperature ?? 0.7,
      maxTokens: agent.maxTokens ?? 4096,
      enabled: agent.enabled,
      isDirty: false,
      savedMessage: null,
      testOutput: null,
      error: null,
    }));
  }, [providerOptions.groups]);

  const handleProviderModelChange = useCallback((provider: string, model: string) => {
    setDraftError(null);
    setState((s) => ({ ...s, provider, model, isDirty: true }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!state.selectedAgent) return;
    if (agentModelSelectionChanged && (state.provider || state.model)) {
      if (!agentModelSelectionAvailable(providerOptions.groups, state.provider, state.model)) {
        setState((s) => ({ ...s, error: 'Selecciona un proveedor/modelo usable confirmado por el backend antes de guardar.' }));
        return;
      }
    }
    setState((s) => ({ ...s, saving: true, error: null, savedMessage: null }));
    try {
      const payload: AgentUpdateRequest = {
        name: state.name,
        systemPrompt: state.systemPrompt,
        model: state.model || null,
        provider: state.provider || null,
        temperature: state.temperature,
        maxTokens: state.maxTokens,
        enabled: state.enabled,
        revision: state.selectedAgent.revision,
      };
      const updated = await client.updateAgent(state.selectedAgent.id, payload);
      setState((s) => ({
        ...s,
        saving: false,
        savedMessage: 'Guardado',
        selectedAgent: updated,
        agents: s.agents.map((a) => (a.id === updated.id ? updated : a)),
        isDirty: false,
      }));
      setTimeout(() => setState((s) => ({ ...s, savedMessage: null })), 2000);
    } catch (e: unknown) {
      const msg = friendlyErrorMessage(e);
      const isConflict = msg.includes('409') || msg.toLowerCase().includes('conflicto');
      setState((s) => ({
        ...s,
        saving: false,
        error: isConflict
          ? 'Conflicto de revisión: otro proceso ha modificado este agente. Recarga e intenta de nuevo.'
          : msg,
      }));
    }
  }, [agentModelSelectionChanged, client, providerOptions.groups, state.selectedAgent, state.name, state.systemPrompt, state.model, state.provider, state.temperature, state.maxTokens, state.enabled]);

  const handleTest = useCallback(async () => {
    if (!state.selectedAgent) return;
    setState((s) => ({ ...s, testing: true, error: null, testOutput: null }));
    try {
      const result = await client.testAgent(state.selectedAgent.id);
      setState((s) => ({
        ...s,
        testing: false,
        testOutput: result.output || `OK — ${result.model} via ${result.provider} · ${result.durationMs}ms`,
      }));
    } catch (e: unknown) {
      setState((s) => ({
        ...s,
        testing: false,
        error: friendlyErrorMessage(e),
      }));
    }
  }, [client, state.selectedAgent]);

  const handleDelete = useCallback(async () => {
    if (!state.selectedAgent) return;
    try {
      await client.deleteAgent(state.selectedAgent.id);
      setConfirmDelete(false);
      setState((s) => ({
        ...s,
        agents: s.agents.filter((a) => a.id !== s.selectedAgent!.id),
        selectedAgent: null,
        name: '', systemPrompt: '', model: '', provider: '',
        temperature: 0.7, maxTokens: 4096, enabled: true,
        isDirty: false, error: null,
      }));
    } catch (e: unknown) {
      setState((s) => ({ ...s, error: friendlyErrorMessage(e) }));
    }
  }, [client, state.selectedAgent]);

  const handleGenerateDraft = useCallback(async () => {
    if (providerOptions.loading) return;
    setDrafting(true);
    setCreationDraft(null);
    setDraftError(null);
    setConfirmDelete(false);
    setState((s) => ({ ...s, selectedAgent: null, saving: false, error: null, savedMessage: null, testOutput: null }));
    try {
      const draft = parseAgentDraft(await client.sendInternalChat(createDraftPrompt(creationGoal.trim(), providerOptions.groups)));
      const selection = resolveAgentModelSelection(providerOptions.groups, state.provider, state.model);
      setCreationDraft(draft);
      setState((s) => ({
        ...s,
        selectedAgent: null,
        name: draft.name,
        systemPrompt: draft.systemPrompt,
        provider: selection?.provider || '',
        model: selection?.model || '',
        temperature: 0.7,
        maxTokens: 4096,
        enabled: true,
        isDirty: true,
      }));
    } catch (e: unknown) {
      setDraftError(friendlyErrorMessage(e, 'No se pudo generar el borrador con IA'));
    } finally {
      setDrafting(false);
    }
  }, [client, creationGoal, providerOptions.groups, providerOptions.loading, state.model, state.provider]);

  const handleCreateFromDraft = useCallback(async () => {
    if (!creationDraft) {
      setDraftError('Genera un borrador con IA antes de crear el agente.');
      return;
    }
    if (!state.name.trim() || !state.systemPrompt.trim()) {
      setDraftError('Revisa el borrador: nombre y system prompt son obligatorios.');
      return;
    }
    if (!agentModelSelectionAvailable(providerOptions.groups, state.provider, state.model)) {
      setDraftError('Selecciona un modelo de un proveedor configurado, habilitado y usable.');
      return;
    }
    setState((s) => ({ ...s, saving: true, error: null, savedMessage: null }));
    setDraftError(null);
    try {
      const created = await client.createAgent({
        name: state.name.trim(),
        systemPrompt: state.systemPrompt.trim(),
        provider: state.provider,
        model: state.model,
        temperature: state.temperature,
        maxTokens: state.maxTokens,
        enabled: state.enabled,
      });
      setCreationDraft(null);
      setState((s) => ({
        ...s,
        saving: false,
        agents: [...s.agents, created],
        selectedAgent: created,
        name: created.name,
        systemPrompt: created.systemPrompt || '',
        model: created.model || '',
        provider: created.provider || '',
        temperature: created.temperature ?? 0.7,
        maxTokens: created.maxTokens ?? 4096,
        enabled: created.enabled,
        isDirty: false,
        savedMessage: 'Agente creado',
        testOutput: null,
        error: null,
      }));
      setTimeout(() => setState((s) => ({ ...s, savedMessage: null })), 2000);
    } catch (e: unknown) {
      setState((s) => ({ ...s, saving: false }));
      setDraftError(friendlyErrorMessage(e, 'No se pudo crear el agente'));
    }
  }, [client, creationDraft, providerOptions.groups, state.enabled, state.maxTokens, state.model, state.name, state.provider, state.systemPrompt, state.temperature]);

  const discardCreationDraft = useCallback(() => {
    setCreationDraft(null);
    setDraftError(null);
    setState((s) => ({
      ...s,
      selectedAgent: null,
      name: '',
      systemPrompt: '',
      model: '',
      provider: '',
      temperature: 0.7,
      maxTokens: 4096,
      enabled: true,
      isDirty: false,
      savedMessage: null,
      testOutput: null,
      error: null,
    }));
  }, []);

  const handleFieldChange = <K extends keyof AgentEditorState>(field: K, value: AgentEditorState[K]) => {
    setDraftError(null);
    setState((s) => ({ ...s, [field]: value, isDirty: true }));
  };

  return (
    <div className="agent-editor-panel" role="region" aria-label="Editor de Agentes">
      <div className="panel-header">
        <h3>Agentes</h3>
        <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Cerrar">
          <Icon name="close" size={16} />
        </button>
      </div>

      <div className="agent-editor-body">
        <div className="agent-list-pane">
          <div className="agent-list-header">
            <span className="agent-list-count">
              {canonicalLoading ? 'Cargando roles…' : canonicalCount ? `${canonicalCount} roles activos` : 'Catálogo de roles no disponible'}
            </span>
            <button
              type="button"
              className="btn btn--primary agent-list-new"
              onClick={() => void handleGenerateDraft()}
              disabled={state.saving || drafting || providerOptions.loading}
            >
              <Icon name={drafting ? 'refresh' : 'plus'} size={12} /> {drafting ? 'Generando…' : 'Nuevo agente con IA'}
            </button>
          </div>
          {state.loading && <div className="panel-loading">Cargando...</div>}
          {!state.loading && !state.selectedAgent && state.error && (
            <div className="form-error" role="alert">{state.error}</div>
          )}
          {!state.loading && !state.error && state.agents.length === 0 && (
            <div className="panel-empty">No hay agentes configurables</div>
          )}
          <ul className="agent-list" role="listbox" aria-label="Lista de agentes">
            {state.agents.map((agent) => (
              <li
                key={agent.id}
                role="option"
                aria-selected={state.selectedAgent?.id === agent.id}
                className={`agent-list-item ${state.selectedAgent?.id === agent.id ? 'is-selected' : ''}`}
                onClick={() => selectAgent(agent)}
              >
                <span className="agent-list-name">{agent.name}</span>
                <span className={`agent-list-status agent-status-${agent.enabled ? 'enabled' : 'disabled'}`}>
                  {agent.enabled ? 'Activo' : 'Inactivo'}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="agent-form-pane">
          {!state.selectedAgent && !creationDraft && (
            <>
              <section className="agent-create-card" aria-labelledby="agent-create-title">
                <span className="agent-create-icon"><Icon name="agents" size={24} /></span>
                <div>
                  <h4 id="agent-create-title">Crear agente con asistencia IA</h4>
                  <p>Primero BAGO genera un nombre y system prompt. Después revisas el borrador, eliges un modelo usable confirmado por backend y solo entonces se crea el agente.</p>
                </div>
                <label className="agent-create-goal" htmlFor="agent-create-goal">
                  <span>Objetivo del agente</span>
                  <textarea
                    id="agent-create-goal"
                    value={creationGoal}
                    onChange={(event) => setCreationGoal(event.target.value)}
                    placeholder="Ej.: revisar PRs, preparar auditorías de frontend, resumir evidencia..."
                    rows={3}
                  />
                </label>
                <ProviderOptionsNotice options={providerOptions} />
                {draftError && <div className="form-error" role="alert">{draftError}</div>}
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={() => void handleGenerateDraft()}
                  disabled={drafting || providerOptions.loading}
                >
                  <Icon name={drafting ? 'refresh' : 'sparkle'} size={14} />
                  {drafting ? 'Generando borrador…' : 'Generar borrador con IA'}
                </button>
              </section>

              {canonicalCatalogue && (
                <section className="agent-canonical-catalogue" aria-label="Roles canónicos de BAGO">
                  <header><strong>Roles canónicos de BAGO</strong><span>Fuente: {String(canonicalCatalogue.source || 'backend')}</span></header>
                  <SubagentCatalogue payload={canonicalCatalogue} />
                </section>
              )}
              {!canonicalCatalogue && canonicalLoading && (
                <div className="agent-form-empty">
                  <Icon name="agents" size={28} />
                  <strong>Cargando roles de BAGO</strong>
                  <p>Consultando el catálogo canónico publicado por el backend.</p>
                </div>
              )}
              {canonicalError && <div className="form-error" role="alert">{canonicalError}</div>}
            </>
          )}

          {!state.selectedAgent && creationDraft && (
            <form
              className="agent-form agent-create-review"
              aria-labelledby="agent-review-title"
              onSubmit={(event) => { event.preventDefault(); void handleCreateFromDraft(); }}
            >
              <div className="agent-review-banner">
                <Icon name="sparkle" size={18} />
                <div>
                  <h4 id="agent-review-title">Revisar borrador generado</h4>
                  <p>Edita nombre, prompt y modelo antes de crear. El POST solo se ejecuta desde este paso.</p>
                </div>
              </div>

              <div className="agent-form-header">
                <div className="form-group form-group--name">
                  <label htmlFor="agent-create-name">Nombre</label>
                  <input
                    id="agent-create-name"
                    type="text"
                    value={state.name}
                    onChange={(e) => handleFieldChange('name', e.target.value)}
                    placeholder="Nombre del agente"
                  />
                </div>

                <div className="form-group form-group--enabled">
                  <label htmlFor="agent-create-enabled" className="toggle-label">
                    <input
                      id="agent-create-enabled"
                      type="checkbox"
                      checked={state.enabled}
                      onChange={(e) => handleFieldChange('enabled', e.target.checked)}
                    />
                    <span>Activo</span>
                  </label>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="agent-create-prompt">System Prompt</label>
                <textarea
                  id="agent-create-prompt"
                  value={state.systemPrompt}
                  onChange={(e) => handleFieldChange('systemPrompt', e.target.value)}
                  placeholder="Instrucciones del agente..."
                  rows={8}
                  className="agent-prompt-textarea"
                />
              </div>

              <ProviderModelFields
                groups={providerOptions.groups}
                provider={state.provider}
                model={state.model}
                disabled={state.saving || providerOptions.loading}
                onChange={handleProviderModelChange}
              />
              <ProviderOptionsNotice options={providerOptions} />

              <div className="agent-form-row">
                <div className="form-group">
                  <label htmlFor="agent-create-temp">Temperatura: {state.temperature}</label>
                  <input
                    id="agent-create-temp"
                    type="range"
                    min={0}
                    max={2}
                    step={0.1}
                    value={state.temperature}
                    onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="agent-create-tokens">Max Tokens: {state.maxTokens}</label>
                  <input
                    id="agent-create-tokens"
                    type="number"
                    min={256}
                    max={128000}
                    value={state.maxTokens}
                    onChange={(e) => handleFieldChange('maxTokens', parseInt(e.target.value, 10))}
                  />
                </div>
              </div>

              {draftError && (
                <div className="form-error" role="alert">
                  <Icon name="alert" size={14} />
                  <span>{draftError}</span>
                </div>
              )}

              <div className="agent-form-actions">
                <button type="button" className="btn btn--ghost" onClick={discardCreationDraft} disabled={state.saving}>
                  Descartar
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => void handleGenerateDraft()} disabled={drafting || state.saving || providerOptions.loading}>
                  <Icon name={drafting ? 'refresh' : 'sparkle'} size={14} />
                  {drafting ? 'Regenerando…' : 'Regenerar'}
                </button>
                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={state.saving || !canCreateDraft}
                >
                  <Icon name={state.saving ? 'refresh' : 'check'} size={14} />
                  {state.saving ? 'Creando…' : 'Crear agente'}
                </button>
              </div>
            </form>
          )}

          {state.selectedAgent && (
            <form
              className="agent-form"
              onSubmit={(e) => { e.preventDefault(); handleSave(); }}
            >
              <div className="agent-form-header">
                <div className="form-group form-group--name">
                  <label htmlFor="agent-name">Nombre</label>
                  <input
                    id="agent-name"
                    type="text"
                    value={state.name}
                    onChange={(e) => handleFieldChange('name', e.target.value)}
                    placeholder="Nombre del agente"
                  />
                </div>

                <div className="form-group form-group--enabled">
                  <label htmlFor="agent-enabled" className="toggle-label">
                    <input
                      id="agent-enabled"
                      type="checkbox"
                      checked={state.enabled}
                      onChange={(e) => handleFieldChange('enabled', e.target.checked)}
                    />
                    <span>Activo</span>
                  </label>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="agent-prompt">System Prompt</label>
                <textarea
                  id="agent-prompt"
                  value={state.systemPrompt}
                  onChange={(e) => handleFieldChange('systemPrompt', e.target.value)}
                  placeholder="Instrucciones del agente..."
                  rows={8}
                  className="agent-prompt-textarea"
                />
              </div>

              <ProviderModelFields
                groups={providerOptions.groups}
                provider={state.provider}
                model={state.model}
                disabled={state.saving || state.testing || providerOptions.loading}
                onChange={handleProviderModelChange}
              />
              <ProviderOptionsNotice options={providerOptions} />
              {currentSelectionUnavailable && (
                <div className="agent-provider-notice is-error" role="alert">
                  El agente apunta a {state.provider || 'proveedor desconocido'} / {state.model || 'modelo desconocido'}, que no está confirmado como usable por el backend.
                </div>
              )}

              <div className="agent-form-row">
                <div className="form-group">
                  <label htmlFor="agent-temp">Temperatura: {state.temperature}</label>
                  <input
                    id="agent-temp"
                    type="range"
                    min={0}
                    max={2}
                    step={0.1}
                    value={state.temperature}
                    onChange={(e) => handleFieldChange('temperature', parseFloat(e.target.value))}
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="agent-tokens">Max Tokens: {state.maxTokens}</label>
                  <input
                    id="agent-tokens"
                    type="number"
                    min={256}
                    max={128000}
                    value={state.maxTokens}
                    onChange={(e) => handleFieldChange('maxTokens', parseInt(e.target.value, 10))}
                  />
                </div>
              </div>

              {state.error && (
                <div className="form-error" role="alert">
                  <Icon name="alert" size={14} />
                  <span>{state.error}</span>
                </div>
              )}

              {state.savedMessage && (
                <div className="form-success" role="status">
                  <Icon name="check" size={14} />
                  <span>{state.savedMessage}</span>
                </div>
              )}

              <div className="agent-form-actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={handleTest}
                  disabled={state.testing}
                  title="Prueba el agente con un mensaje de prueba"
                >
                  <Icon name={state.testing ? 'refresh' : 'sparkle'} size={14} />
                  {state.testing ? 'Probando...' : 'Probar'}
                </button>

                {!confirmDelete ? (
                  <button
                    type="button"
                    className="btn btn--danger"
                    onClick={() => setConfirmDelete(true)}
                    title="Eliminar agente"
                  >
                    <Icon name="alert" size={14} />
                    Eliminar
                  </button>
                ) : (
                  <div className="inline-confirm" role="group" aria-label="Confirmar eliminación">
                    <span className="inline-confirm-label">¿Eliminar "{state.selectedAgent?.name}"?</span>
                    <button
                      type="button"
                      className="btn btn--ghost"
                      onClick={() => setConfirmDelete(false)}
                    >
                      Cancelar
                    </button>
                    <button
                      type="button"
                      className="btn btn--danger"
                      onClick={handleDelete}
                    >
                      Sí, eliminar
                    </button>
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={state.saving || !state.isDirty || (agentModelSelectionChanged && currentSelectionUnavailable)}
                >
                  <Icon name={state.saving ? 'refresh' : 'check'} size={14} />
                  {state.saving ? 'Guardando...' : 'Guardar'}
                </button>
              </div>

              {state.testOutput && (
                <div className="agent-test-output" role="region" aria-label="Resultado de prueba">
                  <div className="agent-test-output-header">
                    <Icon name="sparkle" size={14} />
                    <span>Resultado de prueba</span>
                  </div>
                  <pre className="agent-test-output-body">{state.testOutput}</pre>
                </div>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
