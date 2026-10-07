"""Read source and local Git objects; never import or execute historical BAGO code."""
from __future__ import annotations
import ast
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OWN = OUT.relative_to(ROOT).as_posix() + "/"

def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=check)
    return p.stdout

def digest(b):
    return hashlib.sha256(b).hexdigest()

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def freeze():
    tracked = git("ls-files", "-z").decode().split("\0")
    extra = git("ls-files", "--others", "--exclude-standard", "-z", "--", ".github", "docs/architecture").decode().split("\0")
    paths = sorted({p for p in tracked + extra if p and not p.startswith(OWN)})
    manifest = []
    for p in paths:
        path = ROOT / p
        if path.is_file():
            b = path.read_bytes()
            manifest.append({"path": p, "sha256": digest(b), "bytes": len(b)})
        else:
            manifest.append({"path": p, "missing_or_nonfile": True})
    status = git("status", "--porcelain=v1", "-uno").decode()
    return {
        "schema": "bago.capability-source-freeze.v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("branch", "--show-current").decode().strip(),
        "version": (ROOT / "release_version.txt").read_text().strip(),
        "tracked_status": status,
        "surface_sha256": digest(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()),
        "scope": "All tracked files plus untracked .github and docs/architecture, excluding this audit directory. Logical snapshot; no filesystem lock.",
        "excluded_untracked": ["artifacts/", ".vs/", ".goals/ diagnostics", "backend/.pytest-tmp-audit/", "backend/inventory_report.json", "backend/inventory.err", "nul", "other untracked paths outside .github and docs/architecture"],
        "manifest": manifest,
    }

def read(ref, path):
    if ref == "WORKTREE":
        return (ROOT / path).read_bytes()
    return git("show", f"{ref}:{path}")

def route_rows(content, path):
    tree = ast.parse(content.decode("utf-8-sig"))
    rows = []
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Assign, ast.AnnAssign)):
            continue
        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not set(names) & {"ROUTE_META", "DYNAMIC_ROUTE_META"}:
            continue
        try:
            values = ast.literal_eval(n.value)
        except (ValueError, TypeError):
            continue
        for method, route, module, fn in values:
            rows.append({"method": method, "route": route, "owner_module": module, "handler": fn, "source": path, "line": n.lineno, "registry": names[0]})
    return rows

def collect():
    tags = [t for t in git("tag", "--list", "--sort=version:refname").decode().splitlines() if re.match(r"v\d", t)]
    summaries = []
    allrows = []
    test_index = []
    cli_index = []
    command_index = []
    contracts = []
    source_files = git("ls-files", "-z").decode().split("\0")
    for ref in [*tags, "HEAD", "WORKTREE"]:
        files = source_files if ref == "WORKTREE" else git("ls-tree", "-r", "--name-only", ref).decode().splitlines()
        dispatches = [p for p in ("backend/.bago/api/api_dispatch.py", ".bago/api/api_dispatch.py") if p in files]
        rows = []
        errors = []
        for path in dispatches:
            try:
                rows += route_rows(read(ref, path), path)
            except (SyntaxError, ValueError) as exc:
                errors.append(f"{path}: {exc}")
        for row in rows:
            row["version"] = ref
            row["evidence_level"] = "STATIC_REGISTRY_DECLARATION"
        allrows.extend(rows)
        tests = [p for p in files if (p.startswith(("backend/", "tests/", "frontend/tests/", ".bago/", "bago_core/")) or "/" not in p) and (Path(p).name.startswith("test_") or ".test." in Path(p).name) and p.endswith((".py", ".cjs", ".ts", ".tsx"))]
        contract_paths = [p for p in files if p.startswith(("backend/docs/contracts/", "backend/.bago/contracts/", "backend/contracts/", ".bago/contracts/", ".bago/core/canon/", "backend/.bago/core/canon/", "docs/contracts/")) and p.endswith((".md", ".json"))]
        # File names and object hashes establish presence, not passing tests.
        tree_objects = git("ls-tree", "-r", ref if ref != "WORKTREE" else "HEAD").decode().splitlines()
        blobs = {line.split("\t", 1)[1]: line.split()[2] for line in tree_objects if "\t" in line}
        contracts.extend({"version": ref, "path": p, "git_blob": blobs.get(p), "evidence_level": "CONTRACT_SOURCE_PRESENT"} for p in contract_paths)
        for p in tests:
            test_index.append({"version": ref, "path": p, "git_blob": blobs.get(p), "result": "NOT_RUN"})
        parser_paths = [p for p in files if (p.startswith("backend/bago_core/") or p.startswith("bago_core/")) and ("parser" in Path(p).name or Path(p).name == "launcher.py") and p.endswith(".py")]
        for p in parser_paths:
            try:
                tree = ast.parse(read(ref, p).decode("utf-8-sig"))
                for n in ast.walk(tree):
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_parser" and n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                        cli_index.append({"version": ref, "token": n.args[0].value, "parser_receiver": ast.unparse(n.func.value), "path": p, "line": n.lineno, "evidence_level": "PARSER_DECLARATION_NOT_FULL_DISPATCH"})
            except SyntaxError as exc:
                errors.append(f"{p}: {exc}")
        command_paths = [p for p in ('backend/bago_core/launcher.py','bago_core/launcher.py','backend/.bago/chat/commands.py','.bago/chat/commands.py','.bago/core/cli.py') if p in files]
        for p in command_paths:
            try:
                tree = ast.parse(read(ref,p).decode('utf-8-sig'))
                for n in ast.walk(tree):
                    if not isinstance(n,(ast.Assign,ast.AnnAssign)) or not isinstance(n.value,ast.Dict):
                        continue
                    targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                    names=[t.id for t in targets if isinstance(t,ast.Name)]
                    if not set(names)&{'COMMAND_REGISTRY','_DISPATCH_TABLE','COMMANDS'}:
                        continue
                    for k,v in zip(n.value.keys,n.value.values):
                        if isinstance(k,ast.Constant) and isinstance(k.value,str):
                            command_index.append({'version':ref,'command':k.value,'owner_expression':ast.unparse(v),'source':p,'line':k.lineno,'registry':names[0]})
            except SyntaxError as exc:
                errors.append(f'{p}: {exc}')
        commit = git("rev-parse", f"{ref if ref != 'WORKTREE' else 'HEAD'}^{{commit}}").decode().strip()
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, capture_output=True).returncode == 0
        merge_base = git("merge-base", commit, "HEAD", check=False).decode().strip()
        descendant = subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", commit], cwd=ROOT, capture_output=True).returncode == 0
        relation = "ANCESTOR_OR_HEAD" if ancestor else "DESCENDANT" if descendant else "DIVERGENT" if merge_base else "DISCONNECTED"
        summaries.append({"ref": ref, "commit": commit, "ancestor_of_head": ancestor, "relationship_to_head":relation, "merge_base":merge_base or None, "committed_at": git("show", "-s", "--format=%cI", commit).decode().strip(), "routes": len({(r['method'], r['route']) for r in rows}), "registry_declarations": len(rows), "route_source": dispatches, "route_coverage": "DECLARATIVE_METADATA" if rows else "NO_METADATA_EXTRACTED_REQUIRES_LEGACY_TRACE", "test_files": len(tests), "contract_files": len(contract_paths), "source_errors": errors})
        print(f"{ref}: {summaries[-1]['routes']} routes, {len(tests)} test files", flush=True)
    # Exact route literals are candidate test references; not assertions or coverage proof.
    current = [r for r in allrows if r['version'] == 'WORKTREE']
    literals = {}
    for item in test_index:
        if item['version'] != 'WORKTREE':
            continue
        p = item['path']
        for number, line in enumerate((ROOT / p).read_text(encoding='utf-8-sig', errors='replace').splitlines(), 1):
            for route in re.findall(r'["\'](/[^"\'\s]+)["\']', line):
                literals.setdefault(route, []).append({"path": p, "line": number, "kind": "LITERAL_REFERENCE_ONLY"})
    for row in current:
        row['test_references'] = literals.get(row['route'], [])
        handler_path = str(Path(row['source']).parent / (row['owner_module'] + '.py')).replace('\\', '/')
        row['handler_path'] = handler_path
        row['handler_file_exists'] = (ROOT / handler_path).is_file()
    current_keys = {(r['method'], r['route']) for r in current}
    deltas = []
    for s in summaries:
        if s['ref'] in ('HEAD','WORKTREE') or not s['routes']:
            continue
        old = {(r['method'], r['route']) for r in allrows if r['version'] == s['ref']}
        deltas.append({"version": s['ref'], "ancestor_of_head": s['ancestor_of_head'], "common": len(old & current_keys), "historical_only": sorted(old-current_keys), "current_only": sorted(current_keys-old), "interpretation": "ROUTE_IDENTITY_DELTA_ONLY_NOT_SEMANTIC_CLASSIFICATION"})
    save('versions.json', summaries)
    save('route-history.json', allrows)
    save('current-routes.json', current)
    save('route-deltas.json', deltas)
    save('cli-parser-history.json', cli_index)
    save('command-history.json', command_index)
    save('current-command-surface.json', [r for r in command_index if r['version']=='WORKTREE'])
    save('contract-history.json', contracts)
    save('test-history.json', test_index)
    save('coverage.json', {"local_version_tags":len(tags), "route_metadata_tags":sum(bool(s['routes']) for s in summaries if s['ref'] not in ('HEAD','WORKTREE')), "current_routes":len(current_keys), "current_test_literal_routes":sum(bool(r['test_references']) for r in current), "tests_executed":False, "remote_tags_refreshed":False, "limits":["Local tags only; tag existence does not imply published release", "Legacy inline route dispatch requires manual reconstruction", "Parser tokens are not fully qualified CLI routes", "Route registration and test literals do not prove live functionality", "Semantic matrix is manually traced separately from route extraction"]})

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'freeze':
        if (OUT/'freeze-before.json').exists():
            raise SystemExit('Refusing to overwrite original freeze')
        f = freeze()
        save('freeze-before.json', f)
        print(f['head'], f['surface_sha256'], len(f['manifest']))
    elif mode == 'collect':
        collect()
    elif mode == 'check':
        before = json.loads((OUT/'freeze-before.json').read_text(encoding='utf-8'))
        after = freeze()
        save('freeze-after.json', after)
        ok = before['head'] == after['head'] and before['surface_sha256'] == after['surface_sha256']
        save('freeze-check.json', {'same_head':before['head']==after['head'], 'same_surface':before['surface_sha256']==after['surface_sha256'], 'result':'PASS' if ok else 'CANDIDATE_CHANGED_STOP', 'before':before['surface_sha256'], 'after':after['surface_sha256']})
        print('PASS' if ok else 'CANDIDATE_CHANGED_STOP')
        raise SystemExit(0 if ok else 1)
