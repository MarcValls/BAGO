import { useState, useEffect, useCallback } from 'react';
import type { BagoClient } from '@/api/client';
import type { AgentConfig, AgentUpdateRequest } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';

interface Props {
  client: BagoClient;
  onClose: () => void;
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

export function AgentEditorPanel({ client, onClose }: Props) {
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

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const selectAgent = useCallback((agent: AgentConfig) => {
    setState((s) => ({
      ...s,
      selectedAgent: agent,
      name: agent.name,
      systemPrompt: agent.systemPrompt,
      model: agent.model || '',
      provider: agent.provider || '',
      temperature: agent.temperature ?? 0.7,
      maxTokens: agent.maxTokens ?? 4096,
      enabled: agent.enabled,
      isDirty: false,
      savedMessage: null,
      testOutput: null,
      error: null,
    }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!state.selectedAgent) return;
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
  }, [client, state.selectedAgent, state.name, state.systemPrompt, state.model, state.provider, state.temperature, state.maxTokens, state.enabled]);

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

  const [confirmDelete, setConfirmDelete] = useState(false);

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

  const handleFieldChange = <K extends keyof AgentEditorState>(field: K, value: AgentEditorState[K]) => {
    setState((s) => ({ ...s, [field]: value, isDirty: true }));
  };

  return (
    <div className="agent-editor-panel" role="region" aria-label="Editor de Agentes">
      {/* Header */}
      <div className="panel-header">
        <h3>Agentes</h3>
        <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Cerrar">
          <Icon name="close" size={16} />
        </button>
      </div>

      <div className="agent-editor-body">
        {/* Left: agent list */}
        <div className="agent-list-pane">
          <div className="agent-list-header">
            <span>Agentes</span>
          </div>
          {state.loading && <div className="panel-loading">Cargando...</div>}
          {!state.loading && state.agents.length === 0 && (
            <div className="panel-empty">No hay agentes definidos</div>
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

        {/* Right: editor form */}
        <div className="agent-form-pane">
          {!state.selectedAgent && (
            <div className="agent-form-empty">
              <p>Selecciona un agente para editarlo</p>
            </div>
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

              <div className="agent-form-row">
                <div className="form-group">
                  <label htmlFor="agent-model">Modelo</label>
                  <input
                    id="agent-model"
                    type="text"
                    value={state.model}
                    onChange={(e) => handleFieldChange('model', e.target.value)}
                    placeholder="gpt-4, claude-3..."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="agent-provider">Proveedor</label>
                  <input
                    id="agent-provider"
                    type="text"
                    value={state.provider}
                    onChange={(e) => handleFieldChange('provider', e.target.value)}
                    placeholder="openai, anthropic..."
                  />
                </div>
              </div>

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
                  disabled={state.saving || !state.isDirty}
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
