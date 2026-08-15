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
  const [query, setQuery] = useState('');
  const [toolArgs, setToolArgs] = useState<Record<string, unknown>>({});
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState<ToolResult[]>([]);

  useEffect(() => {
    let cancelled = false;
    void client.runCommand('/commands json').then((result) => {
      const data = result.data && typeof result.data === 'object' ? result.data as Record<string, unknown> : {};
      const names = Array.isArray(data.catalog_commands)
        ? data.catalog_commands
        : Array.isArray(data.registered_commands) ? data.registered_commands : [];
      const catalog = names.map((name) => String(name).trim()).filter(Boolean).map((name) => ({
        cmd: name.startsWith('/') ? name : `/${name}`,
        module: 'BAGO command catalog',
        description: `Ejecutar ${name} con el contexto de la sesión`
      }));
      if (!cancelled) setTools(catalog);
    }).catch((cause) => {
      if (!cancelled) setError(cause instanceof Error ? cause.message : 'No se pudo cargar el catálogo de herramientas.');
    });
    return () => { cancelled = true; };
  }, [client]);

  const visibleTools = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return needle ? tools.filter((tool) => `${tool.cmd} ${tool.description}`.toLowerCase().includes(needle)) : tools;
  }, [query, tools]);
  const selected = useMemo(() => tools.find((t) => t.cmd === selectedTool) || null, [tools, selectedTool]);

  async function runTool() {
    if (!selected) return;
    setBusy(selectedTool);
    setError('');
    setMessage('');
    try {
      const result = await client.runCommand(selected.cmd);
      const output = typeof result.data === 'string' ? result.data : result.message || JSON.stringify(result.data || result, null, 2);
      setResults((current) => [{ tool: selected.cmd, output, success: result.ok !== false && result.state !== 'failed', timestamp: new Date().toISOString() }, ...current].slice(0, 10));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'La herramienta no pudo ejecutarse.');
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
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <div className="tools-list">
            {visibleTools.map((tool) => (
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
