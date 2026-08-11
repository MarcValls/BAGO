import { useEffect, useState } from 'react';
import { Icon } from '@/shared/Icon';

interface Agent {
  id: string;
  name: string;
  description?: string;
  systemPrompt?: string;
  provider?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  enabled: boolean;
  revision: number;
  createdAt: string;
  updatedAt: string;
}

interface AgentEditorPanelProps {
  client?: ReturnType<typeof import('@/api/client').createBagoClient>;
  onClose?: () => void;
}

export function AgentEditorPanel({ client, onClose }: AgentEditorPanelProps) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Agent | null>(null);
  const [form, setForm] = useState<Partial<Agent>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  async function loadAgents() {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      const res = await client.listAgents();
      if (res.agents) setAgents(res.agents as unknown as Agent[]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadAgents(); }, [client]);

  function startCreate() {
    setSelected(null);
    setForm({ name: '', description: '', systemPrompt: '', provider: '', model: '', enabled: true });
  }

  function startEdit(agent: Agent) {
    setSelected(agent);
    setForm({ ...agent });
  }

  async function handleSave() {
    if (!client || !form.name?.trim()) return;
    setSaving(true);
    setError(null);
    try {
      if (selected) {
        await client.updateAgent(selected.id, { ...form, revision: selected.revision });
      } else {
        await client.createAgent(form);
      }
      await loadAgents();
      setSelected(null);
      setForm({});
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(agent: Agent) {
    if (!client) return;
    if (!confirm(`Eliminar agente "${agent.name}"?`)) return;
    try {
      await client.deleteAgent(agent.id);
      await loadAgents();
      if (selected?.id === agent.id) { setSelected(null); setForm({}); }
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleTest() {
    if (!client || !selected) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await client.testAgent(selected.id);
      setTestResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setTestResult(`Error: ${e}`);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="panel agents-panel">
      <div className="panel-header">
        <span className="panel-title">Agentes</span>
        <button type="button" className="btn-icon" onClick={onClose} title="Cerrar"><Icon name="x" /></button>
      </div>

      <div className="panel-body">
        <div className="agents-list">
          <button type="button" className="btn-create-agent" onClick={startCreate}>+ Nuevo agente</button>
          {loading && <div className="panel-loading">Cargando...</div>}
          {!loading && agents.length === 0 && <div className="panel-empty">Sin agentes creados</div>}
          {agents.map((agent) => (
            <div key={agent.id} className={`agent-item ${selected?.id === agent.id ? 'is-selected' : ''}`}>
              <button type="button" className="agent-name-btn" onClick={() => startEdit(agent)}>
                <Icon name={agent.enabled ? 'play-circle' : 'pause-circle'} />
                <span>{agent.name}</span>
              </button>
              <button type="button" className="btn-delete-agent" onClick={() => handleDelete(agent)} title="Eliminar">
                <Icon name="trash" />
              </button>
            </div>
          ))}
        </div>

        {(selected !== null || form.name !== undefined) && (
          <div className="agent-editor">
            <h3>{selected ? `Editar: ${selected.name}` : 'Nuevo agente'}</h3>
            <div className="form-field">
              <label>Nombre</label>
              <input
                type="text"
                value={form.name || ''}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Mi agente"
              />
            </div>
            <div className="form-field">
              <label>Descripción</label>
              <textarea
                value={form.description || ''}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Descripción opcional..."
              />
            </div>
            <div className="form-field">
              <label>System Prompt</label>
              <textarea
                value={form.systemPrompt || ''}
                onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
                placeholder="Eres un asistente útil que..."
              />
            </div>
            <div className="form-row">
              <div className="form-field">
                <label>Provider</label>
                <input
                  type="text"
                  value={form.provider || ''}
                  onChange={(e) => setForm({ ...form, provider: e.target.value })}
                  placeholder="anthropic"
                />
              </div>
              <div className="form-field">
                <label>Modelo</label>
                <input
                  type="text"
                  value={form.model || ''}
                  onChange={(e) => setForm({ ...form, model: e.target.value })}
                  placeholder="claude-sonnet-4"
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-field">
                <label>Temperature</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={form.temperature ?? ''}
                  onChange={(e) => setForm({ ...form, temperature: e.target.value ? parseFloat(e.target.value) : undefined })}
                />
              </div>
              <div className="form-field">
                <label>Max Tokens</label>
                <input
                  type="number"
                  min="1"
                  value={form.maxTokens ?? ''}
                  onChange={(e) => setForm({ ...form, maxTokens: e.target.value ? parseInt(e.target.value) : undefined })}
                />
              </div>
            </div>
            <div className="form-field">
              <label>
                <input
                  type="checkbox"
                  checked={form.enabled ?? true}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                Habilitado
              </label>
            </div>
            {error && <div className="form-error">{error}</div>}
            <div className="form-actions">
              <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
              {selected && (
                <button type="button" className="btn-secondary" onClick={handleTest} disabled={testing}>
                  {testing ? 'Probando...' : 'Probar'}
                </button>
              )}
            </div>
            {testResult && (
              <div className="test-result">
                <pre>{testResult}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
