import { Badge, Icon, ViewState } from '../components/ui'
import { useNodeStatus, useNodeMatrix, useNodePieces, useNodeConnectors, useNodeEvidence } from '../useBagoData'
import { useState } from 'react'
import NodeMapView from './NodeMapView'

const TABS = ['Mapa', 'Matrix', 'Pieces', 'Connectors', 'Evidence']

export default function NodesView({ context, onSetContext, onAction }) {
  const [tab, setTab] = useState('Mapa')
  const { data: statusData, loading: stLoad, error: stErr } = useNodeStatus()
  const { data: matrixData, loading: mxLoad } = useNodeMatrix()
  const { data: piecesData, loading: pcLoad } = useNodePieces()
  const { data: connData, loading: cnLoad } = useNodeConnectors()
  const { data: evidData, loading: evLoad } = useNodeEvidence(40)

  const status = statusData?.ok ? (statusData.data || statusData.text || statusData.raw) : null
  const matrix = matrixData?.ok ? (matrixData.data || matrixData.text) : null
  const pieces = piecesData?.ok ? (piecesData.data || piecesData.text) : null
  const connectors = connData?.ok ? (connData.data || connData.text) : null
  const evidence = evidData?.ok ? (evidData.data || evidData.text) : null

  const loading = { Mapa: false, Matrix: mxLoad, Pieces: pcLoad, Connectors: cnLoad, Evidence: evLoad }[tab]
  const error = stErr || statusData?.error
  const data = { Matrix: matrix, Pieces: pieces, Connectors: connectors, Evidence: evidence }[tab]

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {TABS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${tab === label ? 'is-active' : ''}`} onClick={() => setTab(label)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cp-btn" onClick={() => onAction?.('open-node', context.node)}>Abrir</button>
      </div>

      {tab === 'Mapa' && (
        <NodeMapView context={context} onSetContext={onSetContext} onAction={onAction} />
      )}

      {tab !== 'Mapa' && (
        loading ? (
          <div className="cp-loading">Cargando {tab}…</div>
        ) : error && !data ? (
          <div className="cp-error">Error: {error}</div>
        ) : !data ? (
          <div className="cp-loading">Sin datos — verifica que BAGO runtime esté instalado</div>
        ) : (
          <div className="cp-card cp-node-stage">
            <pre className="cp-json-viewer">{typeof data === 'string' ? data : JSON.stringify(data, null, 2)}</pre>
          </div>
        )
      )}
    </section>
  )
}
