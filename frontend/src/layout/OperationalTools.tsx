import { useEffect, useState, type FormEvent } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';

type RecordValue = Record<string, unknown>;

function asRecord(value: unknown): RecordValue {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
}

function records(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter((item): item is RecordValue => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function Message({ value, error = false }: { value: string; error?: boolean }) {
  return value ? <div className={`system-tool-message ${error ? 'is-error' : ''}`} role={error ? 'alert' : 'status'}>{value}</div> : null;
}

function JsonResult({ value, label = 'Resultado' }: { value: unknown; label?: string }) {
  if (!value) return null;
  return <details className="system-tool-result" open><summary>{label}</summary><pre className="system-json">{JSON.stringify(value, null, 2)}</pre></details>;
}

export function ProviderRuntimeTools({ client }: { client: BagoClient }) {
  const [catalog, setCatalog] = useState<RecordValue | null>(null);
  const [buffer, setBuffer] = useState<RecordValue | null>(null);
  const [model, setModel] = useState('');
  const [policy, setPolicy] = useState<'LRU' | 'SAFE' | 'HARD' | 'KEEP_ACTIVE'>('LRU');
  const [confirmAll, setConfirmAll] = useState(false);
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const loaded = records(buffer?.loaded);

  async function refresh() {
    const [nextCatalog, nextBuffer] = await Promise.all([client.getCatalogStatus(), client.getProviderBufferStatus()]);
    setCatalog(nextCatalog);
    setBuffer(nextBuffer);
  }

  useEffect(() => {
    let active = true;
    Promise.all([client.getCatalogStatus(), client.getProviderBufferStatus()])
      .then(([nextCatalog, nextBuffer]) => { if (active) { setCatalog(nextCatalog); setBuffer(nextBuffer); } })
      .catch((cause) => { if (active) setError(friendlyErrorMessage(cause)); });
    return () => { active = false; };
  }, [client]);

  async function run(key: string, operation: () => Promise<RecordValue>) {
    setBusy(key); setMessage(''); setError('');
    try {
      const result = await operation();
      setMessage(String(result.message || (result.ok === false ? result.error || 'Operación rechazada.' : 'Configuración actualizada.')));
      await refresh();
    } catch (cause) {
      setError(friendlyErrorMessage(cause));
    } finally { setBusy(''); }
  }

  return <div className="system-tool-stack">
    <details className="system-tool-card" data-system-tool="catalog-mode">
      <summary><span className="system-tool-icon"><Icon name="model" size={16} /></span><span className="system-tool-summary"><strong>Visibilidad del catálogo</strong><small>Controla qué modelos aparecen en la UI y el router</small></span><span className="provider-status">{String(catalog?.mode || '…')}</span></summary>
      <div className="system-tool-content">
        <p><code>all</code> permite inspeccionar todo el catálogo; <code>available-only</code> muestra sólo modelos utilizables en esta máquina.</p>
        <div className="system-tool-actions" role="group" aria-label="Modo del catálogo">
          {(['all', 'available-only'] as const).map((mode) => <button key={mode} className={String(catalog?.mode) === mode ? 'primary-button compact' : 'secondary-button compact'} type="button" disabled={Boolean(busy)} onClick={() => void run(`catalog:${mode}`, () => client.setCatalogConfig({ mode }))}>{mode}</button>)}
        </div>
      </div>
    </details>

    <details className="system-tool-card" data-system-tool="model-buffer">
      <summary><span className="system-tool-icon"><Icon name="server" size={16} /></span><span className="system-tool-summary"><strong>Buffer local de modelos</strong><small>Prepara o descarga modelos de Ollama con política explícita</small></span><span className="provider-status">{loaded.length} cargados</span></summary>
      <div className="system-tool-content">
        <form className="system-tool-form" onSubmit={(event) => { event.preventDefault(); if (model.trim()) void run('prepare', () => client.prepareProviderBuffer({ model: model.trim(), policy })); }}>
          <label><span>Modelo</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="qwen3:8b" /></label>
          <label><span>Política</span><select value={policy} onChange={(event) => setPolicy(event.target.value as typeof policy)}><option>LRU</option><option>SAFE</option><option>KEEP_ACTIVE</option><option>HARD</option></select></label>
          <button className="primary-button compact" type="submit" disabled={Boolean(busy) || !model.trim()}><Icon name="plus" size={13} /> Preparar</button>
        </form>
        {loaded.length === 0 ? <div className="system-tool-empty">No hay modelos cargados.</div> : <ul className="system-tool-list">{loaded.map((item) => { const name = String(item.name || 'modelo'); return <li key={name}><span><strong>{name}</strong><small>{String(item.size_gb || 0)} GB · expira {String(item.expires_at || 'sin fecha')}</small></span><button className="text-button danger" type="button" disabled={Boolean(busy)} onClick={() => void run(`unload:${name}`, () => client.unloadProviderBuffer(name))}>Descargar</button></li>; })}</ul>}
        {loaded.length > 0 && (confirmAll ? <div className="system-tool-actions"><button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => { setConfirmAll(false); void run('unload:all', () => client.unloadProviderBuffer()); }}>Confirmar descarga de todos</button><button className="text-button" type="button" onClick={() => setConfirmAll(false)}>Cancelar</button></div> : <button className="text-button danger" type="button" onClick={() => setConfirmAll(true)}>Descargar todos</button>)}
        <Message value={message} /><Message value={error} error />
      </div>
    </details>
  </div>;
}

export function SimulationControls({ client, current, onChanged }: { client: BagoClient; current: RecordValue; onChanged: (value: RecordValue) => void }) {
  const [enabled, setEnabled] = useState(Boolean(current.enabled) && String(current.mode || 'off') !== 'off');
  const [mode, setMode] = useState(String(current.mode || 'off'));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const nextMode = String(current.mode || 'off');
    setMode(nextMode);
    setEnabled(Boolean(current.enabled) && nextMode !== 'off');
  }, [current.enabled, current.mode]);

  async function apply() {
    setBusy(true); setMessage('');
    try {
      const result = await client.setSimulationConfig({ enabled: mode === 'off' ? false : enabled, mode });
      onChanged(result);
      setMessage('Configuración de simulación aplicada. La autoridad continúa en solo observación.');
    } catch (cause) { setMessage(friendlyErrorMessage(cause)); }
    finally { setBusy(false); }
  }

  return <div className="operation-inline-form">
    <label><span>Modo</span><select value={mode} onChange={(event) => { const nextMode = event.target.value; setMode(nextMode); setEnabled(nextMode === 'shadow'); }}><option value="off">Inactivo</option><option value="shadow">Shadow</option></select></label>
    <label className="operation-check"><input type="checkbox" checked={enabled} disabled={mode === 'off'} onChange={(event) => setEnabled(event.target.checked)} /> Registrar observaciones</label>
    <button className="primary-button compact" type="button" disabled={busy} onClick={() => void apply()}>Aplicar</button>
    <Message value={message} error={message.toLowerCase().includes('error')} />
  </div>;
}

export function InterpretControls({ client, onCompleted }: { client: BagoClient; onCompleted: () => Promise<void> }) {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RecordValue | null>(null);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;
    setBusy(true); setError('');
    try {
      const next = await client.postInterpret({ question: question.trim() });
      setResult(next);
      await onCompleted();
    } catch (cause) { setError(friendlyErrorMessage(cause)); }
    finally { setBusy(false); }
  }

  return <div className="system-tool-content operation-action-block">
    <form className="operation-question-form" onSubmit={submit}><label><span>Pregunta para el intérprete reflexivo</span><textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={3} placeholder="¿Qué riesgos o contradicciones contiene esta decisión?" /></label><button className="primary-button compact" type="submit" disabled={busy || !question.trim()}><Icon name="command" size={13} /> Interpretar</button></form>
    <Message value={error} error /><JsonResult value={result} label="Nueva interpretación" />
  </div>;
}

export function MemoryOperations({ client }: { client: BagoClient }) {
  const [status, setStatus] = useState<RecordValue | null>(null);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<RecordValue | null>(null);
  const [memoryId, setMemoryId] = useState('');
  const [content, setContent] = useState('');
  const [vector, setVector] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const knowledge = asRecord(status?.knowledge);
  const embeddings = asRecord(status?.embeddings);

  useEffect(() => {
    let active = true;
    client.getMemoryStatus().then((next) => { if (active) setStatus(next); }).catch((cause) => { if (active) setError(friendlyErrorMessage(cause)); });
    return () => { active = false; };
  }, [client]);

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!query.trim()) return;
    setBusy('search'); setError('');
    try { setResult(await client.searchMemory({ query: query.trim(), limit: 20 })); }
    catch (cause) { setError(friendlyErrorMessage(cause)); }
    finally { setBusy(''); }
  }

  async function upsert(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setMessage('');
    try {
      const parsed = JSON.parse(vector);
      if (!Array.isArray(parsed) || parsed.some((value) => typeof value !== 'number')) throw new Error('El vector debe ser un array JSON de números.');
      setBusy('upsert');
      const next = await client.upsertEmbedding({ memory_id: memoryId.trim(), content: content.trim(), vector: parsed });
      setMessage(`Embedding ${String(next.memory_id || memoryId)} guardado (${String(next.vector_dim || parsed.length)} dimensiones).`);
      setStatus(await client.getMemoryStatus());
    } catch (cause) { setError(friendlyErrorMessage(cause)); }
    finally { setBusy(''); }
  }

  return <section className="system-tab-panel" role="tabpanel">
    <h3>Memoria</h3><p className="system-tab-description">Estado, búsqueda léxica real e ingestión avanzada de embeddings.</p>
    <div className="system-data-grid"><div className="system-data-block"><span className="system-data-label">Memorias activas</span><strong>{String(knowledge.active ?? '—')}</strong></div><div className="system-data-block"><span className="system-data-label">Embeddings</span><strong>{String(embeddings.total ?? '—')}</strong></div><div className="system-data-block"><span className="system-data-label">Búsqueda</span><strong>{String(knowledge.search || '—')}</strong></div></div>
    <form className="operation-question-form" onSubmit={search}><label><span>Buscar en memoria</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="contrato de workspace" /></label><button className="primary-button compact" type="submit" disabled={Boolean(busy) || !query.trim()}><Icon name="search" size={13} /> Buscar</button></form>
    <JsonResult value={result} label="Resultados de memoria" />
    <details className="system-tool-card"><summary><span className="system-tool-icon"><Icon name="bank" size={16} /></span><span className="system-tool-summary"><strong>Ingestar embedding</strong><small>Avanzado: el backend valida y persiste un vector generado externamente</small></span><span className="provider-status">manual</span></summary><form className="system-tool-content operation-embedding-form" onSubmit={upsert}><label><span>ID de memoria</span><input value={memoryId} onChange={(event) => setMemoryId(event.target.value)} required /></label><label><span>Contenido</span><textarea value={content} onChange={(event) => setContent(event.target.value)} rows={3} required /></label><label><span>Vector JSON</span><textarea value={vector} onChange={(event) => setVector(event.target.value)} rows={3} placeholder="[0.12, -0.44, 0.08]" required /></label><button className="secondary-button compact" type="submit" disabled={Boolean(busy) || !memoryId.trim() || !content.trim() || !vector.trim()}>Guardar embedding</button></form></details>
    <Message value={message} /><Message value={error} error />
  </section>;
}

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  return window.btoa(binary);
}

export function VisionOperations({ client }: { client: BagoClient }) {
  const [file, setFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('Describe la imagen y señala cualquier texto o anomalía relevante.');
  const [model, setModel] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RecordValue | null>(null);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!file) return;
    if (file.size > 20 * 1024 * 1024) { setError('La imagen supera el límite de 20 MB.'); return; }
    setBusy(true); setError('');
    try {
      setResult(await client.analyzeVision({ image_base64: toBase64(await file.arrayBuffer()), prompt: prompt.trim(), ...(model.trim() ? { model: model.trim() } : {}) }));
    } catch (cause) { setError(friendlyErrorMessage(cause)); }
    finally { setBusy(false); }
  }

  return <section className="system-tab-panel" role="tabpanel"><h3>Visión</h3><p className="system-tab-description">Analiza una imagen con el modelo de visión local configurado por el backend.</p><form className="vision-form" onSubmit={submit}><label className="vision-file"><span>Imagen</span><input type="file" accept="image/*" onChange={(event) => setFile(event.target.files?.[0] || null)} /><small>{file ? `${file.name} · ${Math.ceil(file.size / 1024)} KB` : 'PNG, JPG, WEBP u otro formato de imagen · máximo 20 MB'}</small></label><label><span>Pregunta</span><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} /></label><label><span>Modelo opcional</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="usa el modelo configurado por defecto" /></label><button className="primary-button compact" type="submit" disabled={busy || !file}><Icon name="review" size={13} /> {busy ? 'Analizando…' : 'Analizar imagen'}</button></form><Message value={error} error />{result && <article className="vision-result"><strong>Respuesta</strong><p>{String(result.response || result.error || 'Sin respuesta')}</p><small>{String(result.model || 'modelo no informado')} · {String(result.duration_ms || '—')} ms</small></article>}</section>;
}

export function SubagentCatalogue({ payload }: { payload: RecordValue }) {
  const agents = records(payload.agents);
  if (payload.error) return <Message value={String(payload.error)} error />;
  if (agents.length === 0) return <div className="system-tool-empty">No hay roles activos registrados.</div>;
  const families = Array.from(new Set(agents.map((agent) => String(agent.family || 'otros'))));
  return <div className="subagent-catalogue">
    <div className="system-tab-meta">{agents.length} roles activos · {families.length} familias · fuente: {String(payload.source || 'backend')}</div>
    <div className="subagent-groups">
      {families.map((family) => {
        const familyAgents = agents.filter((agent) => String(agent.family || 'otros') === family);
        return <section key={family} className="subagent-group">
          <header><strong>{family}</strong><span>{familyAgents.length}</span></header>
          <div className="subagent-list">
            {familyAgents.map((agent) => {
              const tools = Array.isArray(agent.tools) ? agent.tools.map(String) : [];
              const available = agent.available !== false;
              return <details key={String(agent.id)} className="subagent-item">
                <summary>
                  <span><strong>{String(agent.name)}</strong><small>{String(agent.description || 'Rol operativo de BAGO')}</small></span>
                  <span className={`provider-status ${available ? 'is-on' : 'is-off'}`}>{available ? 'activo' : 'no disponible'}</span>
                  <Icon name="chevron" size={12} />
                </summary>
                <div className="subagent-detail">
                  <dl>
                    <div><dt>ID</dt><dd>{String(agent.id)}</dd></div>
                    <div><dt>Versión</dt><dd>{String(agent.version || payload.version || '—')}</dd></div>
                    <div><dt>Origen</dt><dd>{String(agent.source || 'no informado')}</dd></div>
                  </dl>
                  <div className="subagent-tools"><strong>Herramientas</strong>{tools.length ? <div>{tools.map((tool) => <span key={tool}>{tool}</span>)}</div> : <small>Este rol no declara herramientas directas.</small>}</div>
                </div>
              </details>;
            })}
          </div>
        </section>;
      })}
    </div>
  </div>;
}
