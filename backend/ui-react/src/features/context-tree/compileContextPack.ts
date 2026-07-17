// Compilador de packs. Toma un árbol + lista de packs y produce
// markdown listo para enviar al chat. El markdown es deliberadamente
// compacto: cada nodo aparece como bloque con título, tipo, status,
// prioridad y summary. La estructura jerárquica se respeta con
// indentación.
import type {
  ContextCompiledPack,
  ContextNode,
  ContextPack,
  ContextTree
} from './contextTreeTypes';

function indent(level: number): string {
  return '  '.repeat(level);
}

function statusBadge(status: ContextNode['status']): string {
  switch (status) {
    case 'active': return 'ACTIVO';
    case 'proposed': return 'PROPUESTO';
    case 'excluded': return 'EXCLUIDO';
    case 'archived': return 'ARCHIVADO';
    case 'canon': return 'CANON';
    case 'conflict': return 'CONFLICTO';
    case 'stale': return 'STALE';
    default: return status.toUpperCase();
  }
}

function priorityBadge(priority: ContextNode['priority']): string {
  return `prio:${priority}`;
}

function buildTreeMarkdown(tree: ContextTree, rootId: string, level: number): string {
  const lines: string[] = [];
  const node = tree.nodes[rootId];
  if (!node) return '';
  const prefix = indent(level);
  const refs = node.sourceRefs.length
    ? ` refs:${node.sourceRefs.map((ref) => ref.kind + (ref.path ? `:${ref.path}` : '')).join(',')}`
    : '';
  const tags = node.tags.length ? ` tags:${node.tags.join(',')}` : '';
  lines.push(`${prefix}- [${statusBadge(node.status)} | ${priorityBadge(node.priority)}] **${node.title}**${tags}${refs}`);
  if (node.summary) {
    lines.push(`${prefix}  ${node.summary}`);
  }
  if (node.body) {
    for (const line of node.body.split(/\r?\n/)) {
      lines.push(`${prefix}  ${line}`);
    }
  }
  const children = Object.values(tree.nodes)
    .filter((candidate) => candidate.parentId === rootId)
    .sort((a, b) => a.title.localeCompare(b.title, 'es'));
  for (const child of children) {
    lines.push(buildTreeMarkdown(tree, child.id, level + 1));
  }
  return lines.filter(Boolean).join('\n');
}

export function compileContextPack(tree: ContextTree, pack: ContextPack): ContextCompiledPack {
  const stamps = new Date().toISOString();
  const headings: string[] = [];
  headings.push(`# ${pack.name}`);
  headings.push('');
  headings.push(`tree: ${tree.name} (${tree.id})`);
  headings.push(`pack: ${pack.id}`);
  headings.push(`status: ${pack.status}`);
  headings.push(`generated_at: ${stamps}`);
  headings.push(`weight_tokens: ${pack.weightTokens}`);
  headings.push(`nodes: ${pack.nodeIds.length}`);
  headings.push(`conflicts: ${pack.conflicts}`);
  headings.push(`proposals: ${pack.proposals}`);
  headings.push(`stale: ${pack.staleCount}`);
  headings.push('');
  headings.push('## Contexto activo');
  headings.push('');
  // Para nodos en pack, generar árbol solo con esos nodos y sus ancestros
  const inPack = new Set(pack.nodeIds);
  const ancestorsOf = (id: string): Set<string> => {
    const set = new Set<string>();
    let current = tree.nodes[id];
    while (current && current.parentId) {
      set.add(current.parentId);
      current = tree.nodes[current.parentId];
    }
    return set;
  };
  const relevant = new Set<string>([tree.rootId]);
  for (const id of pack.nodeIds) {
    if (!tree.nodes[id]) continue;
    relevant.add(id);
    for (const aid of ancestorsOf(id)) relevant.add(aid);
  }
  // Subárbol compacto: solo mostrar ancestros hasta la raíz y nodos en pack
  const filteredTree: ContextTree = {
    ...tree,
    nodes: Object.fromEntries(
      Object.entries(tree.nodes).filter(([id, node]) => relevant.has(id) || inPack.has(id))
    )
  };
  // Renderizar el árbol a partir de la raíz
  const lines: string[] = [];
  const rootChildren = Object.values(filteredTree.nodes)
    .filter((n) => n.parentId === filteredTree.rootId || n.id === filteredTree.rootId)
    .sort((a, b) => {
      if (a.id === filteredTree.rootId) return -1;
      if (b.id === filteredTree.rootId) return 1;
      return a.title.localeCompare(b.title, 'es');
    });
  for (const child of rootChildren) {
    lines.push(buildTreeMarkdown(filteredTree, child.id, 0));
  }
  if (lines.length) {
    headings.push(lines.join('\n'));
  } else {
    headings.push('(pack vacío)');
  }
  if (pack.notes) {
    headings.push('');
    headings.push('## Notas');
    headings.push('');
    headings.push(pack.notes);
  }
  return {
    id: `cmp_${Math.random().toString(36).slice(2, 10)}`,
    packId: pack.id,
    markdown: headings.join('\n'),
    nodeCount: pack.nodeIds.length,
    weightTokens: pack.weightTokens,
    generatedAt: stamps
  };
}
