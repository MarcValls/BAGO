import { useCallback, useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';
import type {
  CapabilityObjectSchema,
  CapabilityPackageRecord,
  CapabilityReceipt,
  PackageInspection
} from './packageContract';

interface Props {
  client: BagoClient;
}

interface CapabilityExampleRecord {
  id: string;
  name: string;
  version: string;
  description: string;
  kind: 'capability' | 'pipeline';
  execution_mode: 'declarative' | 'executable';
  permissions: string[];
  dependencies: Array<{ id: string; version: string }>;
  schedule_defaults?: Array<{ name: string; schedule_type: 'interval' | 'cron'; interval_s?: number; cron_expr?: string; timezone: string }>;
}

interface SchemaFormProps {
  legend: string;
  schema: CapabilityObjectSchema;
  values: Record<string, unknown>;
  disabled: boolean;
  onChange: (values: Record<string, unknown>) => void;
}

const MAX_PACKAGE_BYTES = 600 * 1024;

function defaultValues(schema: CapabilityObjectSchema, current: Record<string, unknown> = {}): Record<string, unknown> {
  return Object.fromEntries(Object.entries(schema.properties || {}).map(([name, field]) => [
    name,
    current[name] ?? field.default ?? (field.type === 'boolean' ? false : field.type === 'string' ? '' : 0)
  ]));
}

function encodeBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'La operación no pudo completarse.';
}

function SchemaForm({ legend, schema, values, disabled, onChange }: SchemaFormProps) {
  const fields = Object.entries(schema.properties || {});
  if (!fields.length) return <p className="capability-package-muted">{legend}: no requiere campos.</p>;
  return <fieldset className="capability-schema-form" disabled={disabled}>
    <legend>{legend}</legend>
    {fields.map(([name, field]) => {
      const required = schema.required?.includes(name);
      const value = values[name] ?? '';
      const setValue = (next: unknown) => onChange({ ...values, [name]: next });
      return <label key={name}>
        <span>{field.title || name}{required ? ' *' : ''}</span>
        {field.type === 'boolean'
          ? <input type="checkbox" checked={Boolean(value)} onChange={(event) => setValue(event.target.checked)} />
          : field.enum?.length
            ? <select value={String(value)} onChange={(event) => setValue(event.target.value)}>{field.enum.map((option) => <option key={String(option)} value={String(option)}>{String(option)}</option>)}</select>
            : <input
                type={field.type === 'string' ? 'text' : 'number'}
                step={field.type === 'integer' ? '1' : field.type === 'number' ? 'any' : undefined}
                value={String(value)}
                required={required}
                onChange={(event) => setValue(field.type === 'string' ? event.target.value : Number(event.target.value))}
              />}
        {field.description && <small>{field.description}</small>}
      </label>;
    })}
  </fieldset>;
}

function ReceiptView({ receipt }: { receipt: CapabilityReceipt }) {
  return <article className="capability-receipt" data-status={receipt.status}>
    <header><strong>{receipt.status}</strong><span>{receipt.duration_ms} ms</span></header>
    <small>{receipt.receipt_id}</small>
    {receipt.error && <p className="is-error">{receipt.error}</p>}
    {receipt.result !== null && <pre>{typeof receipt.result === 'string' ? receipt.result : JSON.stringify(receipt.result, null, 2)}</pre>}
  </article>;
}

export function ExternalCapabilitiesPanel({ client }: Props) {
  const [packages, setPackages] = useState<CapabilityPackageRecord[]>([]);
  const [receipts, setReceipts] = useState<CapabilityReceipt[]>([]);
  const [examples, setExamples] = useState<CapabilityExampleRecord[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [inspection, setInspection] = useState<PackageInspection | null>(null);
  const [encodedFile, setEncodedFile] = useState('');
  const [activationConfirmed, setActivationConfirmed] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [input, setInput] = useState<Record<string, unknown>>({});
  const [latestReceipt, setLatestReceipt] = useState<CapabilityReceipt | null>(null);
  const [scheduleConfirmed, setScheduleConfirmed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [packageData, receiptData, exampleData] = await Promise.all([
        client.listCapabilityPackages(),
        client.listCapabilityReceipts(),
        client.listCapabilityExamples()
      ]);
      const packageRecords = Array.isArray(packageData.packages) ? packageData.packages as CapabilityPackageRecord[] : [];
      const receiptRecords = Array.isArray(receiptData.receipts) ? receiptData.receipts as CapabilityReceipt[] : [];
      const exampleRecords = Array.isArray(exampleData.examples) ? exampleData.examples as CapabilityExampleRecord[] : [];
      setPackages(packageRecords);
      setReceipts(receiptRecords);
      setExamples(exampleRecords);
      setSelectedId((current) => current && packageRecords.some((item) => item.id === current) ? current : packageRecords[0]?.id || '');
      setError('');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => { void load(); }, [load]);

  const selected = useMemo(() => packages.find((item) => item.id === selectedId) || null, [packages, selectedId]);
  const selectedReceipts = useMemo(() => receipts.filter((item) => (item.capability_id === selectedId || item.pipeline_id === selectedId) && item.capability_version === selected?.version).slice(0, 5), [receipts, selectedId, selected?.version]);

  useEffect(() => {
    if (!selected) return;
    setConfig(defaultValues(selected.configuration_schema || { type: 'object', properties: {}, required: [] }, selected.config));
    setInput(defaultValues(selected.input_schema || { type: 'object', properties: {}, required: [] }));
    setConfirmed(false);
    setActivationConfirmed(false);
    setLatestReceipt(null);
    setScheduleConfirmed(false);
  }, [selected?.id, selected?.digest]);

  const runAction = async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setBusy('');
    }
  };

  const installExample = (example: CapabilityExampleRecord) => runAction(`example:${example.id}`, async () => {
    const response = await client.installCapabilityExample(example.id);
    const installed = response.package && typeof response.package === 'object' ? response.package as Record<string, unknown> : {};
    setSelectedId(String(installed.id || example.id));
    setNotice(response.already_installed ? 'El ejemplo ya estaba instalado.' : 'Ejemplo instalado sin activar. Revisa confianza y permisos.');
    await load();
  });

  const importPackage = () => runAction('import', async () => {
    if (!file) throw new Error('Selecciona un archivo ZIP.');
    if (file.size > MAX_PACKAGE_BYTES) throw new Error('El ZIP supera el límite de 600 KB.');
    const contentBase64 = encodedFile || encodeBase64(await file.arrayBuffer());
    const preview = inspection || await client.inspectCapabilityPackage(file.name, contentBase64);
    if (!preview.ok) throw new Error(preview.errors?.[0]?.message || 'El paquete no supera la inspección.');
    const response = await client.importCapabilityPackage({ fileName: file.name, contentBase64, confirmTrust: false });
    setNotice(response.already_installed ? 'El mismo paquete ya estaba instalado.' : 'Paquete importado. Revisa las advertencias antes de activarlo.');
    setSelectedId(response.package.id);
    setFile(null);
    setFileInputKey((value) => value + 1);
    setInspection(null);
    setEncodedFile('');
    await load();
  });

  const inspectFile = (nextFile: File | null) => {
    setFile(nextFile);
    setInspection(null);
    setEncodedFile('');
    if (!nextFile) return;
    void runAction('inspect', async () => {
      if (nextFile.size > MAX_PACKAGE_BYTES) throw new Error('El ZIP supera el límite de 600 KB.');
      const contentBase64 = encodeBase64(await nextFile.arrayBuffer());
      const preview = await client.inspectCapabilityPackage(nextFile.name, contentBase64);
      setEncodedFile(contentBase64);
      setInspection(preview);
      if (!preview.ok) throw new Error(preview.errors?.[0]?.message || 'El paquete no supera la inspección.');
      setNotice('Inspección completada. Importar no activa ni ejecuta el paquete.');
    });
  };

  const toggleEnabled = () => selected && runAction('enable', async () => {
    await client.setCapabilityPackageEnabled(selected.id, !selected.enabled, selected.enabled ? false : activationConfirmed);
    setNotice(selected.enabled ? 'Paquete desactivado.' : 'Paquete activado.');
    setActivationConfirmed(false);
    await load();
  });

  const saveConfig = () => selected && runAction('configure', async () => {
    await client.configureCapabilityPackage(selected.id, config);
    setNotice('Configuración guardada por el backend.');
    await load();
  });

  const execute = () => selected && runAction('execute', async () => {
    const response = await client.executeCapabilityPackage(selected.id, { input, confirmed, approved_permissions: selected.permissions });
    setLatestReceipt(response.receipt);
    setNotice(response.ok ? 'Ejecución completada con receipt.' : 'La ejecución terminó con error; se conservó el receipt.');
    setConfirmed(false);
    await load();
  });

  const createSuggestedSchedule = (suggestion: NonNullable<CapabilityPackageRecord['schedule_defaults']>[number]) => selected && runAction('schedule', async () => {
    if (!scheduleConfirmed) throw new Error('Confirma la creación de la programación.');
    const response = await client.createSchedule({
      name: suggestion.name,
      target_type: selected.kind === 'pipeline' ? 'pipeline' : 'capability',
      target: selected.kind === 'pipeline' ? { pipeline_id: selected.id, input } : { capability_id: selected.id, input },
      schedule_type: suggestion.schedule_type,
      interval_s: suggestion.interval_s,
      cron_expr: suggestion.cron_expr,
      timezone: suggestion.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      enabled: true,
      confirmed: true,
      approved_permissions: selected.permissions
    });
    setScheduleConfirmed(false);
    setNotice(`Programación creada: ${String(response.schedule && typeof response.schedule === 'object' ? (response.schedule as Record<string, unknown>).name : suggestion.name)}.`);
  });

  const exportSelected = () => selected && runAction('export', async () => {
    const response = await client.exportCapabilityPackage(selected.id);
    const content = String(response.content_base64 || '');
    const fileName = String(response.file_name || `${selected.id}-${selected.version}.bago.zip`);
    if (!content) throw new Error('El backend no devolvió el contenido exportado.');
    const binary = atob(content);
    const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(url);
    setNotice(`Paquete exportado con digest ${String(response.digest || '').slice(0, 12)}.`);
  });

  return <div className="capability-packages">
    <aside className="capability-package-catalog">
      <form className="capability-package-import" onSubmit={(event) => { event.preventDefault(); void importPackage(); }}>
        <header><Icon name="pack" size={15} /><strong>Importar paquete</strong></header>
        <input key={fileInputKey} aria-label="Paquete ZIP" type="file" accept=".zip,application/zip" onChange={(event) => inspectFile(event.target.files?.[0] || null)} />
        <small>ZIP BAGO Package v1 o capability.json legado · máximo 600 KB</small>
        {inspection && <div className={`capability-inspection ${inspection.ok ? 'is-ok' : 'is-error'}`}>
          <strong>{inspection.identity?.name || 'Paquete'}</strong>
          <span>{inspection.kind} · {inspection.execution_mode} · firma {inspection.signature_state} · digest {inspection.digest_state}</span>
          <small>{inspection.files?.length || 0} archivos · {inspection.permissions?.length ? `permisos: ${inspection.permissions.join(', ')}` : 'sin permisos'}</small>
          {inspection.warnings?.map((warning) => <em key={warning}>{warning}</em>)}
        </div>}
        <button className="primary-button compact" type="submit" disabled={!file || !inspection?.ok || Boolean(busy)}>{busy === 'inspect' ? 'Inspeccionando…' : busy === 'import' ? 'Importando…' : 'Importar sin activar'}</button>
      </form>
      <section className="capability-example-list" aria-label="Ejemplos incluidos">
        <header><strong>Ejemplos incluidos</strong><span>{examples.length}</span></header>
        {examples.map((example) => {
          const installed = packages.some((item) => item.id === example.id);
          return <article key={example.id}>
            <span><strong>{example.name}</strong><small>{example.kind} · {example.description}</small></span>
            <button className="text-button" type="button" disabled={installed || Boolean(busy)} onClick={() => void installExample(example)}>{installed ? 'Instalado' : busy === `example:${example.id}` ? 'Instalando…' : 'Instalar'}</button>
          </article>;
        })}
      </section>
      <div className="capability-package-list" aria-label="Capacidades externas">
        <header><strong>Instaladas</strong><button className="icon-button" type="button" aria-label="Actualizar capacidades" onClick={() => void load()}><Icon name="refresh" size={13} /></button></header>
        {loading && <p>Consultando backend…</p>}
        {!loading && !packages.length && <p>No hay paquetes instalados.</p>}
        {packages.map((item) => <button key={item.id} type="button" className={selectedId === item.id ? 'is-selected' : ''} onClick={() => setSelectedId(item.id)}>
          <span className={`status-orb ${item.enabled ? 'state-confirmed' : ''}`} />
          <span><strong>{item.name}</strong><small>{item.id} · v{item.version}</small></span>
        </button>)}
      </div>
    </aside>

    <main className="capability-package-detail">
      {(error || notice) && <div className={`capability-package-message ${error ? 'is-error' : 'is-ok'}`} role={error ? 'alert' : 'status'}>{error || notice}</div>}
      {!selected && !loading && <div className="capability-package-empty"><Icon name="pack" size={24} /><strong>Importa una capacidad para comenzar</strong><p>La interfaz se genera desde su manifest; no se carga JavaScript externo.</p></div>}
      {selected && <>
        <header className="capability-package-title">
          <div><span>{selected.kind === 'pipeline' ? 'PIPELINE' : 'CAPACIDAD'} EXTERNA · {selected.author}</span><h3>{selected.name}</h3><p>{selected.description}</p></div>
          <div className="capability-package-title-actions">
            <button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => void exportSelected()}><Icon name="pack" size={12} /> Exportar</button>
            <button className={selected.enabled ? 'secondary-button compact' : 'primary-button compact'} type="button" disabled={Boolean(busy) || !selected.available || (!selected.enabled && !activationConfirmed)} onClick={() => void toggleEnabled()}>{busy === 'enable' ? 'Guardando…' : selected.enabled ? 'Desactivar' : 'Activar'}</button>
          </div>
        </header>
        {!selected.available && <p className="capability-package-message is-error">{selected.error}</p>}
        {selected.warnings?.map((warning) => <p key={warning} className="capability-package-message is-warning">{warning}</p>)}
        <div className="capability-package-metadata">
          <span><b>Ejecución</b>{selected.execution_mode || selected.runtime?.kind || 'declarative'}{selected.runtime?.entrypoint ? ` · ${selected.runtime.entrypoint}` : ''}</span>
          <span><b>Confianza</b>{selected.trust_state || 'untrusted'} · firma {selected.signature_state || 'unsigned'}</span>
          <span><b>Permisos solicitados</b>{selected.permissions.length ? selected.permissions.join(', ') : 'ninguno'}</span>
          <span><b>Integridad</b>{selected.digest_state || 'unknown'} · {selected.digest.slice(0, 12)}</span>
          <span><b>Dependencias</b>{selected.dependencies?.length ? selected.dependencies.map((item) => `${item.id}@${item.version}`).join(', ') : 'ninguna'}</span>
          <span><b>Estado</b>{selected.last_status}</span>
        </div>
        {!selected.enabled && <label className="capability-package-check capability-activation-check"><input type="checkbox" checked={activationConfirmed} onChange={(event) => setActivationConfirmed(event.target.checked)} /><span>Confío en el origen, código y permisos mostrados para activar este paquete</span></label>}
        <div className="capability-package-workbench">
          <section>
            <SchemaForm legend="Configuración" schema={selected.configuration_schema || { type: 'object', properties: {}, required: [] }} values={config} disabled={Boolean(busy)} onChange={setConfig} />
            <button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => void saveConfig()}>{busy === 'configure' ? 'Guardando…' : 'Guardar configuración'}</button>
          </section>
          <section>
            <SchemaForm legend="Entrada" schema={selected.input_schema || { type: 'object', properties: {}, required: [] }} values={input} disabled={Boolean(busy) || !selected.enabled} onChange={setInput} />
            <label className="capability-package-check"><input type="checkbox" checked={confirmed} disabled={!selected.enabled || Boolean(busy)} onChange={(event) => setConfirmed(event.target.checked)} /><span>Confirmo esta ejecución{selected.permissions.length ? ` y sus permisos: ${selected.permissions.join(', ')}` : ''}</span></label>
            <button className="primary-button compact" type="button" disabled={!selected.enabled || !confirmed || Boolean(busy)} onClick={() => void execute()}>{busy === 'execute' ? 'Ejecutando…' : 'Ejecutar con receipt'}</button>
          </section>
        </div>
        {selected.schedule_defaults?.length ? <section className="capability-package-schedules">
          <header><strong>Programación sugerida</strong><span>No se activa durante la importación</span></header>
          {selected.schedule_defaults.map((suggestion) => <article key={`${suggestion.name}-${suggestion.cron_expr || suggestion.interval_s}`}>
            <span><strong>{suggestion.name}</strong><small>{suggestion.schedule_type === 'cron' ? suggestion.cron_expr : `cada ${Math.round(Number(suggestion.interval_s || 0) / 60)} minutos`} · {suggestion.timezone}</small></span>
            <button className="secondary-button compact" type="button" disabled={!selected.enabled || !scheduleConfirmed || Boolean(busy)} onClick={() => void createSuggestedSchedule(suggestion)}>{busy === 'schedule' ? 'Creando…' : 'Crear programación'}</button>
          </article>)}
          <label className="capability-package-check"><input type="checkbox" checked={scheduleConfirmed} disabled={!selected.enabled || Boolean(busy)} onChange={(event) => setScheduleConfirmed(event.target.checked)} /><span>Confirmo que BAGO podrá ejecutar este paquete automáticamente</span></label>
        </section> : null}
        <section className="capability-package-results">
          <header><strong>Resultado y evidencia</strong><span>{selectedReceipts.length} receipts recientes</span></header>
          {latestReceipt && <ReceiptView receipt={latestReceipt} />}
          {!latestReceipt && selectedReceipts[0] && <ReceiptView receipt={selectedReceipts[0]} />}
          {!latestReceipt && !selectedReceipts.length && <p className="capability-package-muted">Todavía no hay ejecuciones.</p>}
        </section>
      </>}
    </main>
  </div>;
}
