import { useCallback, useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';
import type {
  CapabilityObjectSchema,
  CapabilityPackageRecord,
  CapabilityReceipt
} from './packageContract';

interface Props {
  client: BagoClient;
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
  const [selectedId, setSelectedId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [trust, setTrust] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [input, setInput] = useState<Record<string, unknown>>({});
  const [latestReceipt, setLatestReceipt] = useState<CapabilityReceipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [packageData, receiptData] = await Promise.all([
        client.listCapabilityPackages(),
        client.listCapabilityReceipts()
      ]);
      setPackages(packageData.packages);
      setReceipts(receiptData.receipts);
      setSelectedId((current) => current && packageData.packages.some((item) => item.id === current) ? current : packageData.packages[0]?.id || '');
      setError('');
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => { void load(); }, [load]);

  const selected = useMemo(() => packages.find((item) => item.id === selectedId) || null, [packages, selectedId]);
  const selectedReceipts = useMemo(() => receipts.filter((item) => item.capability_id === selectedId && item.capability_version === selected?.version).slice(0, 5), [receipts, selectedId, selected?.version]);

  useEffect(() => {
    if (!selected) return;
    setConfig(defaultValues(selected.configuration_schema, selected.config));
    setInput(defaultValues(selected.input_schema));
    setConfirmed(false);
    setLatestReceipt(null);
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

  const importPackage = () => runAction('import', async () => {
    if (!file) throw new Error('Selecciona un archivo ZIP.');
    if (file.size > MAX_PACKAGE_BYTES) throw new Error('El ZIP supera el límite de 600 KB.');
    if (!trust) throw new Error('Confirma que confías en el código del paquete.');
    const response = await client.importCapabilityPackage(file.name, encodeBase64(await file.arrayBuffer()), true);
    setNotice(response.already_installed ? 'El mismo paquete ya estaba instalado.' : 'Paquete importado y pendiente de activación.');
    setSelectedId(response.package.id);
    setFile(null);
    setFileInputKey((value) => value + 1);
    setTrust(false);
    await load();
  });

  const toggleEnabled = () => selected && runAction('enable', async () => {
    await client.setCapabilityPackageEnabled(selected.id, !selected.enabled);
    setNotice(selected.enabled ? 'Capacidad desactivada.' : 'Capacidad activada.');
    await load();
  });

  const saveConfig = () => selected && runAction('configure', async () => {
    await client.configureCapabilityPackage(selected.id, config);
    setNotice('Configuración guardada por el backend.');
    await load();
  });

  const execute = () => selected && runAction('execute', async () => {
    const response = await client.executeCapabilityPackage(selected.id, input, confirmed, selected.permissions);
    setLatestReceipt(response.receipt);
    setNotice(response.ok ? 'Ejecución completada con receipt.' : 'La ejecución terminó con error; se conservó el receipt.');
    setConfirmed(false);
    await load();
  });

  return <div className="capability-packages">
    <aside className="capability-package-catalog">
      <form className="capability-package-import" onSubmit={(event) => { event.preventDefault(); void importPackage(); }}>
        <header><Icon name="pack" size={15} /><strong>Importar paquete</strong></header>
        <input key={fileInputKey} aria-label="Paquete ZIP" type="file" accept=".zip,application/zip" onChange={(event) => setFile(event.target.files?.[0] || null)} />
        <small>ZIP ≤ 600 KB · capability.json + runner Python</small>
        <label className="capability-package-check"><input type="checkbox" checked={trust} onChange={(event) => setTrust(event.target.checked)} /><span>Confío en este código local</span></label>
        <button className="primary-button compact" type="submit" disabled={!file || !trust || Boolean(busy)}>{busy === 'import' ? 'Importando…' : 'Importar'}</button>
      </form>
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
          <div><span>EXTERNA · {selected.author}</span><h3>{selected.name}</h3><p>{selected.description}</p></div>
          <button className={selected.enabled ? 'secondary-button compact' : 'primary-button compact'} type="button" disabled={Boolean(busy) || !selected.available} onClick={() => void toggleEnabled()}>{busy === 'enable' ? 'Guardando…' : selected.enabled ? 'Desactivar' : 'Activar'}</button>
        </header>
        {!selected.available && <p className="capability-package-message is-error">{selected.error}</p>}
        <div className="capability-package-metadata">
          <span><b>Runner</b>{selected.runtime.kind} · {selected.runtime.entrypoint}</span>
          <span><b>Estado</b>{selected.last_status}</span>
          <span><b>Permisos solicitados</b>{selected.permissions.length ? selected.permissions.join(', ') : 'ninguno'}</span>
        </div>
        <div className="capability-package-workbench">
          <section>
            <SchemaForm legend="Configuración" schema={selected.configuration_schema} values={config} disabled={Boolean(busy)} onChange={setConfig} />
            <button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => void saveConfig()}>{busy === 'configure' ? 'Guardando…' : 'Guardar configuración'}</button>
          </section>
          <section>
            <SchemaForm legend="Entrada" schema={selected.input_schema} values={input} disabled={Boolean(busy) || !selected.enabled} onChange={setInput} />
            <label className="capability-package-check"><input type="checkbox" checked={confirmed} disabled={!selected.enabled || Boolean(busy)} onChange={(event) => setConfirmed(event.target.checked)} /><span>Confirmo esta ejecución{selected.permissions.length ? ` y sus permisos: ${selected.permissions.join(', ')}` : ''}</span></label>
            <button className="primary-button compact" type="button" disabled={!selected.enabled || !confirmed || Boolean(busy)} onClick={() => void execute()}>{busy === 'execute' ? 'Ejecutando…' : 'Ejecutar con receipt'}</button>
          </section>
        </div>
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
