import { useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';

interface ToolRecord {
  cmd: string;
  module: string;
  description: string;
  preflight?: Array<{ kind: string; value: string; severity?: string }>;
  schema?: Record<string, unknown>;
}

interface ToolResult {
  tool: string;
  output: string;
  success: boolean;
  timestamp: string;
}

interface Props {
  client: BagoClient;
}

export function ToolsPanel({ client }: Props) {
  const [tools, setTools] = useState<ToolRecord[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>('');
  const [toolArgs, setToolArgs] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState<ToolResult[]>([]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const payload = await client.getToolsRegistry();
        const toolsList = Array.isArray(payload.tools) ? payload.tools : [];
        if (active) setTools(toolsList as ToolRecord[]);
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : String(cause));
      }
    })();
    return () => { active = false; };
  }, [client]);

  const selected = useMemo(() => tools.find((t) => t.cmd === selectedTool) || null, [tools, selectedTool]);

  async function runTool() {
    if (!selected) return;
    setBusy(selectedTool);
    setError('');
    setMessage('');
    try {
      const result = await client.executeTool(selectedTool, toolArgs);
      const output = typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2);
      const toolResult: ToolResult = {
        tool: selectedTool,
        output,
        success: result.success === true,
        timestamp: new Date().toISOString()
      };
      setResults((prev) => [toolResult, ...prev].slice(0, 10));
      setMessage(`Herramienta ${selectedTool} ejecutada`);
      setToolArgs({});
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy('');
    }
  }

  function getSchemaFields(schema?: Record<string, unknown>) {
    if (!schema) return [];
    const props = schema.properties as Record<string, { type?: string; description?: string; required?: boolean }> | undefined;
    if (!props) return [];
    const required = Array.isArray(schema.required) ? schema.required : [];
    return Object.entries(props).map(([name, field]) => ({
      name,
      type: field?.type || 'string',
      description: field?.description || '',
      required: required.includes(name)
    }));
  }

  const schemaFields = getSchemaFields(selected?.schema);

  return (
    <div className="tools-panel">
      <header className="tools-panel-header">
        <strong>Herramientas</strong>
        <span>{tools.length} disponibles</span>
      </header>

      <div className="tools-panel-layout">
        <aside className="tools-catalog">
          <div className="tools-search">
            <Icon name="search" size={14} />
            <input
              type="text"
              placeholder="Buscar herramienta..."
              value={selectedTool}
              onChange={(e) => { setSelectedTool(e.target.value); setToolArgs({}); }}
            />
          </div>
          <div className="tools-list">
            {tools.map((tool) => (
              <button
                key={tool.cmd}
                type="button"
                className={selectedTool === tool.cmd ? 'is-selected' : ''}
                onClick={() => { setSelectedTool(tool.cmd); setToolArgs({}); }}
              >
                <strong>{tool.cmd}</strong>
                <small>{tool.description}</small>
              </button>
            ))}
          </div>
        </aside>

        <main className="tools-detail">
          {(error || message) && (
            <div className={`tools-message ${error ? 'is-error' : 'is-ok'}`} role={error ? 'alert' : 'status'}>
              {error || message}
            </div>
          )}

          {!selected ? (
            <div className="tools-empty">
              <Icon name="tools" size={32} />
              <strong>Selecciona una herramienta</strong>
              <p>Ejecuta herramientas de análisis, código, seguridad, etc.</p>
            </div>
          ) : (
            <>
              <header className="tools-detail-header">
                <div>
                  <span>HERRAMIENTA</span>
                  <h3>{selected.cmd}</h3>
                  <p>{selected.description}</p>
                </div>
              </header>

              {schemaFields.length > 0 && (
                <div className="tools-form">
                  <div className="tools-section-header">Parámetros</div>
                  <div className="tools-form-grid">
                    {schemaFields.map((field) => (
                      <label key={field.name}>
                        <span>{field.name}{field.required ? ' *' : ''}</span>
                        {field.type === 'boolean' ? (
                          <input
                            type="checkbox"
                            checked={Boolean(toolArgs[field.name])}
                            onChange={(e) => setToolArgs({ ...toolArgs, [field.name]: e.target.checked })}
                          />
                        ) : field.type === 'number' ? (
                          <input
                            type="number"
                            value={String(toolArgs[field.name] ?? '')}
                            onChange={(e) => setToolArgs({ ...toolArgs, [field.name]: Number(e.target.value) })}
                          />
                        ) : (
                          <input
                            type="text"
                            value={String(toolArgs[field.name] ?? '')}
                            onChange={(e) => setToolArgs({ ...toolArgs, [field.name]: e.target.value })}
                            placeholder={field.description}
                          />
                        )}
                        {field.description && <small>{field.description}</small>}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="tools-actions">
                <button
                  className="primary-button"
                  type="button"
                  disabled={Boolean(busy)}
                  onClick={runTool}
                >
                  {busy === selectedTool ? 'Ejecutando…' : 'Ejecutar herramienta'}
                </button>
              </div>

              {results.length > 0 && (
                <div className="tools-results">
                  <div className="tools-section-header">Resultados recientes</div>
                  <div className="tools-results-list">
                    {results.map((result, index) => (
                      <article key={index} className="tools-result">
                        <header>
                          <strong>{result.tool}</strong>
                          <span className={result.success ? 'state-ok' : 'state-error'}>
                            {result.success ? '✓' : '✗'}
                          </span>
                          <small>{new Date(result.timestamp).toLocaleTimeString()}</small>
                        </header>
                        <pre>{result.output}</pre>
                      </article>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
