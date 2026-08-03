import { useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import type { SelectionRecord } from '@/contracts/backend';
import { Icon, type IconName } from '@/shared/Icon';
import { CapabilityContractError, validateCapabilitySnapshot, type CapabilityPiece, type CapabilityRoute, type CapabilitySnapshot } from './contract';
import { ExternalCapabilitiesPanel } from './ExternalCapabilitiesPanel';

interface Props {
  client: BagoClient;
  onInspect: (selection: SelectionRecord) => void;
}

type CapabilityTab = 'anatomy' | 'routes' | 'contract' | 'external';

const CAPABILITY_TABS = [['anatomy', 'Anatomía'], ['routes', 'Rutas'], ['contract', 'Contrato'], ['external', 'Externas']] as const;

function pieceIcon(piece: CapabilityPiece): IconName {
  if (piece.type === 'input') return 'inbox';
  if (piece.type === 'output') return 'artifact';
  if (piece.implementation.kind === 'agent') return 'sparkle';
  if (piece.implementation.kind === 'script') return 'command';
  if (piece.implementation.kind === 'validator') return 'verified';
  return 'cog';
}

function pieceSelection(piece: CapabilityPiece, snapshot: CapabilitySnapshot): SelectionRecord {
  return {
    id: piece.id,
    kind: 'capability-piece',
    targetKind: 'graph.node',
    title: piece.name,
    summary: piece.purpose,
    detail: [
      `tipo: ${piece.type}`,
      `implementación: ${piece.implementation.kind}`,
      `disponibilidad: ${piece.availability}`,
      `autoridad: ${snapshot.source.authority}`,
      `ejecución: ${snapshot.runtime_snapshot.run_state}`
    ],
    raw: piece
  };
}

export function CapabilityAnatomyModule(props: Props) {
  const [snapshot, setSnapshot] = useState<CapabilitySnapshot | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<CapabilityTab>('anatomy');
  const [selectedPieceId, setSelectedPieceId] = useState('');
  const [selectedRouteId, setSelectedRouteId] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    props.client.listCapabilities()
      .then((list) => {
        const first = list.capabilities[0];
        if (!first) throw new CapabilityContractError('El backend no publicó capacidades.');
        return props.client.getCapability(first.id);
      })
      .then((raw) => {
        if (cancelled) return;
        const next = validateCapabilitySnapshot(raw);
        setSnapshot(next);
        setSelectedPieceId(next.pieces.find((piece) => !['input', 'output'].includes(piece.type))?.id || next.pieces[0]?.id || '');
        setSelectedRouteId(next.governance.recommended_route_id || next.routes[0]?.id || '');
        setError('');
      })
      .catch((reason) => {
        if (!cancelled) setError(reason instanceof Error ? reason.message : 'No se pudo cargar la anatomía.');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [props.client]);

  const pieceById = useMemo(() => new Map(snapshot?.pieces.map((piece) => [piece.id, piece]) || []), [snapshot]);
  const selectedRoute = snapshot?.routes.find((route) => route.id === selectedRouteId) || snapshot?.routes[0] || null;
  const selectedPiece = snapshot?.pieces.find((piece) => piece.id === selectedPieceId) || null;
  const operativePieces = snapshot?.pieces.filter((piece) => !['input', 'output'].includes(piece.type)) || [];

  const inspectPiece = (piece: CapabilityPiece) => {
    if (!snapshot) return;
    setSelectedPieceId(piece.id);
    props.onInspect(pieceSelection(piece, snapshot));
  };

  if (loading) return <div className="capability-state"><Icon name="refresh" size={22} /><strong>Construyendo anatomía desde el backend…</strong></div>;
  if (error || !snapshot) return <section className="capability-anatomy">
    <header className="capability-heading"><div><span>BACKEND</span><h2>Capacidades</h2><p>Inventario interno y paquetes externos gobernados.</p></div></header>
    <nav className="capability-tabs" aria-label="Vista de capacidad">
      {CAPABILITY_TABS.map(([id, label]) => <button key={id} type="button" className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>{label}</button>)}
    </nav>
    {tab === 'external'
      ? <ExternalCapabilitiesPanel client={props.client} />
      : <div className="capability-state is-error" role="alert"><Icon name="warning" size={22} /><strong>Anatomía interna no disponible</strong><p>{error}</p></div>}
    <footer><span><Icon name="shield" size={12} /> El backend conserva autoridad sobre instalación y ejecución.</span></footer>
  </section>;

  return <section className="capability-anatomy">
    <header className="capability-heading">
      <div><span>{tab === 'external' ? 'PAQUETES LOCALES · BACKEND' : 'BACKEND · SOLO LECTURA'}</span><h2>{tab === 'external' ? 'Capacidades externas' : snapshot.capability.name}</h2><p>{tab === 'external' ? 'Importa, activa y ejecuta extensiones con confirmación y receipt.' : snapshot.capability.description}</p></div>
      <div><span><Icon name="lock" size={12} /> {tab === 'external' ? 'bago.capability/v1' : snapshot.contract_version}</span><b>{tab === 'external' ? 'UI declarativa · runner aislado del renderer' : `${operativePieces.length} piezas · ${snapshot.routes.length} rutas`}</b></div>
    </header>
    <nav className="capability-tabs" aria-label="Vista de capacidad">
      {CAPABILITY_TABS.map(([id, label]) => <button key={id} type="button" className={tab === id ? 'is-active' : ''} onClick={() => setTab(id)}>{label}</button>)}
    </nav>

    {tab === 'anatomy' && <div className="capability-anatomy-view">
      <section className="capability-route-focus">
        <header><span>RUTA SELECCIONADA</span><strong>{selectedRoute?.name || 'Sin ruta'}</strong><small>{selectedRoute?.description}</small></header>
        <div className="capability-flow">
          {selectedRoute?.steps.map((pieceId, index) => {
            const piece = pieceById.get(pieceId);
            if (!piece) return null;
            return <div key={piece.id} className="capability-flow-step"><button type="button" className={selectedPieceId === piece.id ? 'is-selected' : ''} onClick={() => inspectPiece(piece)}><Icon name={pieceIcon(piece)} size={16} /><span><small>{piece.type}</small><strong>{piece.name}</strong></span></button>{index < selectedRoute.steps.length - 1 && <Icon name="arrowRight" size={16} />}</div>;
          })}
        </div>
      </section>
      <section className="capability-piece-library">
        <header><strong>Piezas observadas</strong><span>Disponibilidad no implica ejecución</span></header>
        <div>{operativePieces.map((piece) => <button key={piece.id} type="button" className={selectedPieceId === piece.id ? 'is-selected' : ''} data-availability={piece.availability} onClick={() => inspectPiece(piece)}><Icon name={pieceIcon(piece)} size={14} /><span><strong>{piece.name}</strong><small>{piece.implementation.kind} · {piece.availability}</small></span></button>)}</div>
      </section>
    </div>}

    {tab === 'routes' && <div className="capability-routes">
      {snapshot.routes.map((route: CapabilityRoute) => <button key={route.id} type="button" className={selectedRoute?.id === route.id ? 'is-selected' : ''} onClick={() => { setSelectedRouteId(route.id); setTab('anatomy'); }}><b>{route.priority}</b><span><strong>{route.name}</strong><small>{route.condition}</small><em>{route.steps.map((id) => pieceById.get(id)?.name || id).join(' → ')}</em></span><i data-availability={route.availability}>{route.availability}</i></button>)}
    </div>}

    {tab === 'contract' && <div className="capability-contract-view">
      <div className="capability-contract-grid">
        <article><span>Definición</span><strong>{snapshot.capability.definition_state}</strong><p>No demuestra ejecución.</p></article>
        <article><span>Ejecución</span><strong>{snapshot.runtime_snapshot.run_state}</strong><p>{snapshot.runtime_snapshot.receipt_id ? `Receipt ${snapshot.runtime_snapshot.receipt_id}` : 'Sin execution_id ni receipt.'}</p></article>
        <article><span>Autoridad</span><strong>{snapshot.source.authority}</strong><p>{snapshot.source.provenance}</p></article>
        <article><span>Persistencia</span><strong>{snapshot.host_binding.persistence_root}</strong><p>La vista no escribe estado.</p></article>
      </div>
      <details><summary>Snapshot contractual</summary><pre>{JSON.stringify(snapshot, null, 2)}</pre></details>
    </div>}

    {tab === 'external' && <ExternalCapabilitiesPanel client={props.client} />}

    <footer><span><Icon name="shield" size={12} /> {tab === 'external' ? 'La UI declara intención; el backend valida, ejecuta y emite el receipt.' : 'La UI inspecciona; ejecución y verificación pertenecen al backend.'}</span>{tab !== 'external' && selectedPiece && <small>{selectedPiece.implementation.ref || selectedPiece.id}</small>}</footer>
  </section>;
}
