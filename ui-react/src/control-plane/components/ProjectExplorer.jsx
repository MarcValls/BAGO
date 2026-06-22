import { useEffect, useMemo, useState } from 'react'
import { Icon } from './ui'
import { chatApi } from '../../api'

function buildTree(entries) {
  const root = { name: '', path: '', type: 'directory', children: {} }
  for (const entry of entries) {
    const parts = entry.path.split('/')
    let node = root
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isLast = i === parts.length - 1
      if (!node.children[part]) {
        node.children[part] = {
          name: part,
          path: parts.slice(0, i + 1).join('/'),
          type: isLast ? entry.type : 'directory',
          children: {},
        }
      }
      node = node.children[part]
    }
  }
  return root
}

function sortNodes(nodes) {
  return [...nodes].sort((a, b) => {
    if (a.type === b.type) return a.name.localeCompare(b.name)
    return a.type === 'directory' ? -1 : 1
  })
}

function TreeNode({ node, depth, selectedFile, onSelect, expanded, setExpanded }) {
  if (node.type === 'file') {
    const isSelected = selectedFile?.path === node.path
    return (
      <button
        type="button"
        className={`cp-explorer-node cp-explorer-file ${isSelected ? 'is-selected' : ''}`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => onSelect(node)}
        title={node.path}
      >
        <Icon name="file" size={14} />
        <span className="cp-explorer-label">{node.name}</span>
      </button>
    )
  }

  const isOpen = expanded.has(node.path)
  const childNodes = sortNodes(Object.values(node.children || {}))

  return (
    <div className="cp-explorer-dir">
      <button
        type="button"
        className="cp-explorer-node cp-explorer-dir-head"
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => {
          setExpanded((prev) => {
            const next = new Set(prev)
            if (next.has(node.path)) next.delete(node.path)
            else next.add(node.path)
            return next
          })
        }}
        title={node.path || 'Proyecto'}
      >
        <span className={`cp-explorer-chevron ${isOpen ? 'is-open' : ''}`}>▶</span>
        <Icon name={node.path ? 'folder' : 'project'} size={14} />
        <span className="cp-explorer-label">{node.name || 'Proyecto'}</span>
      </button>
      {isOpen ? (
        <div className="cp-explorer-children">
          {childNodes.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedFile={selectedFile}
              onSelect={onSelect}
              expanded={expanded}
              setExpanded={setExpanded}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default function ProjectExplorer({ selectedFile, onSelectFile, onSendToChat }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(() => new Set(['']))

  useEffect(() => {
    let active = true
    chatApi.listFiles()
      .then((data) => {
        if (!active) return
        setEntries(Array.isArray(data) ? data : (data.entries || []))
        setError('')
      })
      .catch((err) => {
        if (!active) return
        setError(err.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => { active = false }
  }, [])

  const tree = useMemo(() => buildTree(entries), [entries])

  if (loading) return <div className="cp-explorer"><div className="cp-explorer-status">Cargando proyecto…</div></div>
  if (error) return <div className="cp-explorer"><div className="cp-explorer-status cp-explorer-error">{error}</div></div>

  return (
    <div className="cp-explorer">
      <div className="cp-explorer-head">
        <span>Explorador</span>
        {selectedFile ? (
          <button
            type="button"
            className="cp-explorer-send"
            onClick={() => onSendToChat?.(selectedFile)}
            title="Enviar archivo al chat"
          >
            <Icon name="chat" size={12} />
          </button>
        ) : null}
      </div>
      <div className="cp-explorer-body">
        <TreeNode
          node={tree}
          depth={0}
          selectedFile={selectedFile}
          onSelect={onSelectFile}
          expanded={expanded}
          setExpanded={setExpanded}
        />
      </div>
    </div>
  )
}
