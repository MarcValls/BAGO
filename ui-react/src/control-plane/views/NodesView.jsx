import { useState } from 'react'
import { useNodeStatus, useNodeMatrix, useNodePieces, useNodeConnectors, useNodeEvidence } from '../useBagoData'
import NodeMapView from './NodeMapView'

const TABS = ['Mapa', 'Matrix', 'Pieces', 'Connectors', 'Evidence']

export default function NodesView({ context, onSetContext, onAction }) {
  const [tab, setTab] = useState('Mapa')
  const [validationResult, setValidationResult] = useState(null)
  const { data: statusData, loading: statusLoading, error: statusError, refresh: refreshStatus } = useNodeStatus()
  const { data: matrixData, loading: matrixLoading, refresh: refreshMatrix } = useNodeMatrix()
  const { data: piecesData, loading: piecesLoading, refresh: refreshPieces } = useNodePieces()
  const { data: connectorsData, loading: connectorsLoading, refresh: refreshConnectors } = useNodeConnectors()
  const { data: evidenceData, loading: evidenceLoading, refresh: refreshEvidence } = useNodeEvidence(40)

  const status = statusData?.ok ? (statusData.data || statusData.text || statusData.raw) : null
  const matrix = matrixData?.ok ? (matrixData.data || matrixData.text) : null
  const pieces = piecesData?.ok ? (piecesData.data || piecesData.text) : null
  const connectors = connectorsData?.ok ? (connectorsData.data || connectorsData.text) : null
  const evidence = evidenceData?.ok ? (evidenceData.data || evidenceData.text) : null

  const loading = { Mapa: statusLoading, Matrix: matrixLoading, Pieces: piecesLoading, Connectors: connectorsLoading, Evidence: evidenceLoading }[tab]
  const error = statusError || statusData?.error
  const data = { Mapa: status, Matrix: matrix, Pieces: pieces, Connectors: connectors, Evidence: evidence }[tab]

  async function refreshAll() {
    await Promise.all([refreshStatus(), refreshMatrix(), refreshPieces(), refreshConnectors(), refreshEvidence()])
  }

  async function validate() {
    const result = await onAction?.('validate-nodes')
    if (result !== null) {
      setValidationResult(result)
      await refreshAll()
    }
  }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {TABS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${tab === label ? 'is-active' : ''}`} onClick={() => setTab(label)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cp-btn" onClick={refreshAll}>Refrescar</button>
        <button type="button" className="cp-btn cp-btn-primary" onClick={validate}>Validar nodos</button>
      </div>

      {tab === 'Mapa' && <NodeMapView context={context} onSetContext={onSetContext} onAction={onAction} />}

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

      {validationResult ? (
        <div className="cp-card cp-node-stage">
          <div className="cp-section-title">Última validación</div>
          <pre className="cp-json-viewer">{typeof validationResult === 'string' ? validationResult : JSON.stringify(validationResult, null, 2)}</pre>
        </div>
      ) : null}
    </section>
  )
}
