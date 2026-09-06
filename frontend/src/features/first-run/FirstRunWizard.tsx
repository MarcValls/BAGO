import { useMemo, useState } from 'react';
import type { BackendProviders, UiBootstrapSnapshot } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';
import { firstRunInitialStep, firstRunProviderOptions, firstRunReadiness } from './firstRun';
import { useProjectInspection } from '@/features/workspace/useProjectInspection';
import type { BagoClient } from '@/api/client';
import { WorkspacePickerDialog } from '@/features/workspace/WorkspacePickerDialog';

interface Props {
  snapshot: UiBootstrapSnapshot | null;
  providers: BackendProviders | null;
  busy: boolean;
  onRefresh: () => Promise<void> | void;
  onConfigureProvider: (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }) => Promise<void>;
  onTestProvider: (provider: string, config: { base_url?: string; api_key?: string; model?: string }) => Promise<{ ok: boolean; detail?: string }>;
  onActivateWorkspace: (root: string) => Promise<boolean>;
  onCreateDemo: (root: string) => Promise<boolean>;
  client: BagoClient;
  onChooseWorkspace?: (defaultPath?: string) => Promise<string | null>;
  onFinish: () => void;
  onClose: () => void;
}

const STEPS = ['Comprobar', 'Proveedor', 'Proyecto', 'Listo'];

export function FirstRunWizard(props: Props) {
  const [step, setStep] = useState(() => firstRunInitialStep(props.snapshot));
  const [providerId, setProviderId] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [projectRoot, setProjectRoot] = useState('');
  const [message, setMessage] = useState('');
  const [working, setWorking] = useState(false);
  const [workspacePickerOpen, setWorkspacePickerOpen] = useState(false);
  const [tested, setTested] = useState<Record<string, { ok: boolean; detail: string }>>({});
  const options = useMemo(() => firstRunProviderOptions(props.providers), [props.providers]);
  const readiness = firstRunReadiness(props.snapshot);
  const inspection = useProjectInspection(projectRoot, props.client);

  const chooseProvider = (id: string) => {
    setProviderId(id);
    const option = options.find((item) => item.id === id);
    setBaseUrl(option?.baseUrl || (id === 'ollama-local' ? 'http://127.0.0.1:11434' : ''));
  };

  const saveProvider = async () => {
    if (!providerId) return;
    setWorking(true);
    setMessage('');
    try {
      await props.onConfigureProvider(providerId, {
        enabled: true,
        base_url: baseUrl.trim() || undefined,
        api_key: apiKey.trim() || undefined,
        model: model.trim() || undefined
      });
      setMessage(`${options.find((item) => item.id === providerId)?.label || providerId} configurado`);
      setStep(2);
    } catch (error) {
      setMessage(friendlyErrorMessage(error, 'No se pudo configurar el proveedor'));
    } finally {
      setWorking(false);
    }
  };

  const testProvider = async (id = providerId) => {
    if (!id) return;
    setWorking(true);
    try {
      const result = await props.onTestProvider(id, {
        base_url: id === providerId ? baseUrl.trim() || undefined : undefined,
        api_key: id === providerId ? apiKey.trim() || undefined : undefined,
        model: id === providerId ? model.trim() || undefined : undefined
      });
      setTested((current) => ({ ...current, [id]: { ok: result.ok, detail: result.detail || (result.ok ? 'Responde correctamente' : 'No responde') } }));
      setMessage(result.ok ? `${id} responde correctamente` : `${id}: ${result.detail || 'no responde'}`);
    } catch (error) {
      setTested((current) => ({ ...current, [id]: { ok: false, detail: friendlyErrorMessage(error, 'No se pudo probar el proveedor') } }));
    } finally { setWorking(false); }
  };

  const inspectionLabel = (() => {
    if (inspection.kind === 'loading') return 'Inspeccionando…';
    if (inspection.kind === 'error') return inspection.message || 'No se pudo inspeccionar';
    if (inspection.kind !== 'ready') return '';
    if (inspection.configured && inspection.linked && inspection.bindingConfirmed) return '✓ Configurado y vinculado';
    if (inspection.configured) return '⚠ Necesita vinculación';
    return '⚠ Carpeta nueva — se sembrará al activar';
  })();

  const isInspectionReady = inspection.kind === 'ready' && Boolean(inspection.configured && inspection.linked && inspection.bindingConfirmed);

  const activateWorkspace = async (selectedRoot = projectRoot) => {
    if (!selectedRoot.trim()) {
      setMessage('Indica una ruta absoluta para el proyecto.');
      return;
    }
    setWorking(true);
    setMessage('');
    try {
      const ok = await props.onActivateWorkspace(selectedRoot.trim());
      if (ok) {
        setMessage('Proyecto activado');
        setStep(3);
      } else setMessage('BAGO no pudo activar el proyecto. Revisa la ruta.');
    } catch (error) {
      setMessage(friendlyErrorMessage(error, 'BAGO no pudo activar el proyecto'));
    } finally {
      setWorking(false);
    }
  };

  const prepareProject = async (demo: boolean, selectedRoot = projectRoot) => {
    if (!selectedRoot.trim()) {
      setMessage('Indica una ruta absoluta para el proyecto.');
      return;
    }
    setWorking(true);
    setMessage('');
    try {
      const ok = demo ? await props.onCreateDemo(selectedRoot.trim()) : await props.onActivateWorkspace(selectedRoot.trim());
      if (ok) {
        setMessage(demo ? 'Proyecto demo creado y activado' : 'Proyecto activado');
        setStep(3);
      } else setMessage('BAGO no pudo activar el proyecto. Revisa la ruta.');
    } catch (error) {
      setMessage(friendlyErrorMessage(error, 'BAGO no pudo activar el proyecto'));
    } finally {
      setWorking(false);
    }
  };

  return (<>
    <div className="first-run-backdrop" role="dialog" aria-modal="true" aria-labelledby="first-run-title">
      <section className="first-run-wizard">
        <header className="first-run-head">
          <div><span className="first-run-eyebrow">Primera puesta en marcha</span><h2 id="first-run-title">Prepara BAGO en pocos minutos</h2></div>
          <button type="button" className="icon-button" onClick={props.onClose} aria-label="Cerrar recorrido"><Icon name="close" size={17} /></button>
        </header>
        <ol className="first-run-steps" aria-label="Progreso">
          {STEPS.map((label, index) => <li key={label} className={index === step ? 'active' : index < step ? 'done' : ''}><span>{index < step ? '✓' : index + 1}</span>{label}</li>)}
        </ol>
        <div className="first-run-content">
          {step === 0 && <div className="first-run-panel">
            <h3>Comprobación del entorno</h3><p>BAGO comprueba el backend, el proveedor y el workspace. No instala nada sin tu acción.</p>
            <div className="first-run-checks">
              <StatusRow ok={readiness.backend} label="Backend de BAGO" detail={readiness.backend ? 'Disponible' : 'No responde'} />
              <StatusRow ok={readiness.provider} label="Proveedor de IA" detail={readiness.provider ? `${props.snapshot?.model.provider || 'Configurado'} · ${props.snapshot?.model.effectiveModel || props.snapshot?.model.configuredModel || ''}` : 'Necesita configuración'} />
              <StatusRow ok={readiness.workspace} label="Workspace" detail={readiness.workspace ? 'Vinculado y válido' : 'Usa uno existente o crea el demo'} />
            </div>
            <button type="button" className="secondary-button" onClick={() => void props.onRefresh()} disabled={props.busy}>Volver a comprobar</button>
          </div>}
          {step === 1 && <div className="first-run-panel">
            <h3>Conecta un proveedor</h3><p>Elige el proveedor que realmente quieres usar. Ollama local es opcional.</p>
            <div className="first-run-provider-matrix" aria-label="Estado de proveedores">
              {options.map((item) => {
                const live = tested[item.id];
                const status = !item.enabled ? 'Deshabilitado' : live?.ok ? 'Responde correctamente' : item.configured ? 'Configurado' : item.modelCount ? 'Catálogo disponible' : item.authKind === 'none' ? 'Listo para configurar' : 'Credenciales ausentes';
                return <div className="first-run-provider-row" key={item.id}><div><strong>{item.label}</strong><small>{status} · {item.modelCount} modelos</small></div><button type="button" className="text-button" onClick={() => { chooseProvider(item.id); void testProvider(item.id); }} disabled={working}>Probar ahora</button></div>;
              })}
            </div>
            <label className="first-run-field"><span>Proveedor</span><select value={providerId} onChange={(event) => chooseProvider(event.target.value)}><option value="">Selecciona un proveedor</option>{options.map((item) => <option key={item.id} value={item.id}>{item.label}{item.configured ? ' · configurado' : ''}</option>)}</select></label>
            {providerId && <><label className="first-run-field"><span>URL base (si aplica)</span><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label><label className="first-run-field"><span>API key (si aplica)</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" /></label><label className="first-run-field"><span>Modelo preferido (opcional)</span><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Se detectará si lo dejas vacío" /></label><div className="first-run-actions"><button type="button" className="secondary-button" onClick={() => void testProvider()} disabled={working}>Probar proveedor ahora</button><button type="button" className="primary-button" onClick={() => void saveProvider()} disabled={working}>Guardar proveedor</button></div></>}
          </div>}
          {step === 2 && <div className="first-run-panel">
            <h3>Activa tu primer proyecto</h3><p>Usa una carpeta existente o crea una demo ejecutable desde cero.</p>
            <label className="first-run-field"><span>Ruta absoluta</span><input value={projectRoot} onChange={(event) => setProjectRoot(event.target.value)} placeholder="C:\\Users\\tu_usuario\\Documents\\BAGO-Demo" /></label>
            {projectRoot.trim() && inspectionLabel && <p className={`first-run-inspection ${inspection.kind === 'error' ? 'is-error' : isInspectionReady ? 'is-ok' : ''}`} role="status">{inspectionLabel}</p>}
            <button type="button" className="secondary-button" onClick={() => setWorkspacePickerOpen(true)}><Icon name="folder" size={14} /> Examinar carpetas</button>
            <div className="first-run-actions">
              {isInspectionReady
                ? <button type="button" className="primary-button" onClick={() => void activateWorkspace()} disabled={working}>Activar workspace</button>
                : <><button type="button" className="secondary-button" onClick={() => void activateWorkspace()} disabled={working || inspection.kind === 'loading'}>Usar proyecto existente</button><button type="button" className="primary-button" onClick={() => void prepareProject(true)} disabled={working}>Crear proyecto demo</button></>}
            </div>
            {!isInspectionReady && <small>La demo solo se crea si la carpeta no existe o está vacía.</small>}
          </div>}
          {step === 3 && <div className="first-run-panel first-run-ready"><span className="first-run-ready-icon"><Icon name="check" size={28} /></span><h3>BAGO está listo</h3><p>Ya puedes conversar, reunir contexto y convertir decisiones en tareas del Pipeline.</p><button type="button" className="primary-button" onClick={props.onFinish}>Entrar en BAGO</button></div>}
          {message && <p className="first-run-message" role="status">{message}</p>}
        </div>
        {step < 3 && <footer className="first-run-foot"><button type="button" className="text-button" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>Atrás</button><button type="button" className="primary-button" onClick={() => setStep(Math.min(3, step + 1))}>Continuar</button></footer>}
      </section>
    </div>
    {workspacePickerOpen && <WorkspacePickerDialog value={projectRoot} onChange={setProjectRoot} onClose={() => setWorkspacePickerOpen(false)} onChooseExplorer={props.onChooseWorkspace} onConfirm={() => { setWorkspacePickerOpen(false); void activateWorkspace(projectRoot); }} client={props.client} mode="select" title="Selecciona y activa tu primer proyecto" />}
  </>);
}

function StatusRow({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return <div className={`first-run-status ${ok ? 'ok' : 'pending'}`}><span>{ok ? '✓' : '!'}</span><div><strong>{label}</strong><small>{detail}</small></div></div>;
}
