import { Icon } from './ui'
import { ROOMS, TITLES } from './constants'
import ChatView from '../../components/ChatView'
import DashboardView from '../views/DashboardView'
import InstallationsView from '../views/InstallationsView'
import PatchbayView from '../views/PatchbayView'
import NodesView from '../views/NodesView'
import PiecesView from '../views/PiecesView'
import ReleasesView from '../views/ReleasesView'
import AuditView from '../views/AuditView'
import HealthView from '../views/HealthView'
import JobsView from '../views/JobsView'

export default function EditorArea({
  activeRoom, navigate, searchRef,
  context, setContext, onAction, onOpenTerminal,
  chatControl, chatCenter,
  selectedFile, selectedFileContent, selectedFileLoading,
  onCloseFile,
}) {
  return (
    <main className="cp-editor">
      <div className="cp-editor-tabs">
        <button
          type="button"
          className={`cp-editor-tab ${activeRoom === 'chat' ? 'is-active' : ''}`}
          onClick={() => navigate('chat')}
        >
          <Icon name="chat" size={14} /> Chat
        </button>
        {activeRoom !== 'chat' && (
          <button type="button" className="cp-editor-tab is-active">
            <Icon name={(ROOMS.find((r) => r.id === activeRoom) || {}).icon || 'dashboard'} size={14} />
            {TITLES[activeRoom] || activeRoom}
            <span className="cp-editor-tab-close" onClick={(e) => { e.stopPropagation(); navigate('chat') }}>×</span>
          </button>
        )}
        {selectedFile && (
          <button type="button" className={`cp-editor-tab ${activeRoom === 'file' ? 'is-active' : ''}`} onClick={() => navigate('file')}>
            <Icon name="file" size={14} />
            {selectedFile.name}
            <span className="cp-editor-tab-close" onClick={(e) => { e.stopPropagation(); onCloseFile?.() }}>×</span>
          </button>
        )}
        <div className="cp-editor-tabs-spacer" />
        <button type="button" className="cp-editor-ctrl" title="Buscar" onClick={() => searchRef.current?.focus()}>
          <Icon name="search" size={14} />
        </button>
      </div>

      <div className="cp-editor-body">
        {activeRoom === 'chat' && (
          <div className="cp-chat-panel">
            <ChatView control={chatControl} center={chatCenter} />
          </div>
        )}
        {activeRoom === 'file' && selectedFile && (
          <div className="cp-file-viewer">
            <div className="cp-file-head">
              <Icon name="file" size={14} />
              <span>{selectedFile.path}</span>
            </div>
            {selectedFileLoading ? (
              <div className="cp-loading">Cargando archivo…</div>
            ) : (
              <pre className="cp-file-content">{selectedFileContent}</pre>
            )}
          </div>
        )}
        {activeRoom === 'dashboard' && <DashboardView context={context} onSetContext={setContext} onAction={onAction} />}
        {activeRoom === 'installations' && (
          <InstallationsView context={context} onSetContext={setContext} onAction={onAction} onOpenTerminal={onOpenTerminal} />
        )}
        {activeRoom === 'patchbay' && <PatchbayView context={context} onSetContext={setContext} />}
        {activeRoom === 'nodes' && <NodesView context={context} onSetContext={setContext} onAction={onAction} />}
        {activeRoom === 'pieces' && <PiecesView context={context} onAction={onAction} />}
        {activeRoom === 'releases' && <ReleasesView context={context} onAction={onAction} />}
        {activeRoom === 'audit' && <AuditView context={context} onAction={onAction} />}
        {activeRoom === 'health' && <HealthView context={context} onSetContext={setContext} />}
        {activeRoom === 'jobs' && <JobsView context={context} onAction={onAction} />}
      </div>
    </main>
  )
}