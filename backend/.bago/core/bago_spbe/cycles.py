from __future__ import annotations

from collections import defaultdict
from .model import BoundedCycleContract, CycleClassification, DependencyCycle, DependencyEdge


class SemanticCycleValidator:
    CYCLE_RELATIONS = {"REQUIRES", "DEPENDS_ON", "SEMANTIC_BASIS"}

    def detect(
        self,
        edges: tuple[DependencyEdge, ...],
        bounded: tuple[BoundedCycleContract, ...] = (),
        benign: tuple[frozenset[str], ...] = (),
    ) -> tuple[DependencyCycle, ...]:
        relevant = [e for e in edges if e.relation in self.CYCLE_RELATIONS]
        graph: dict[str, list[DependencyEdge]] = defaultdict(list)
        for e in relevant:
            graph[e.source_id].append(e)

        cycles: dict[frozenset[str], list[DependencyEdge]] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str):
            visited.add(node)
            stack.append(node)
            on_stack.add(node)
            for edge in graph.get(node, []):
                nxt = edge.target_id
                if nxt not in visited:
                    dfs(nxt)
                elif nxt in on_stack:
                    idx = stack.index(nxt)
                    nodes = stack[idx:] + [nxt]
                    key = frozenset(nodes)
                    if key not in cycles:
                        cyc_edges = []
                        for i in range(len(nodes)-1):
                            src, dst = nodes[i], nodes[i+1]
                            match = next((x for x in graph[src] if x.target_id == dst), None)
                            if match:
                                cyc_edges.append(match)
                        cycles[key] = cyc_edges
            stack.pop()
            on_stack.remove(node)

        for n in list(graph):
            if n not in visited:
                dfs(n)

        bounded_sets = {c.nodes for c in bounded}
        benign_sets = set(benign)
        results = []
        for nodes, cyc_edges in cycles.items():
            if nodes in benign_sets:
                cls = CycleClassification.BENIGN_REFERENCE_CYCLE
            elif nodes in bounded_sets:
                cls = CycleClassification.BOUNDED_ITERATIVE_CYCLE
            else:
                cls = CycleClassification.INVALID_CYCLE
            results.append(DependencyCycle(
                node_refs=tuple(sorted(nodes)),
                classification=cls,
                relation_types=tuple(sorted({e.relation for e in cyc_edges})),
                detection_evidence=tuple(f"{e.source_id}->{e.target_id}:{e.relation}" for e in cyc_edges),
            ))
        return tuple(results)
