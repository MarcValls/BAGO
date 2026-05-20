import subprocess, json, os, sys
from pathlib import Path

def api_json(url):
    r = subprocess.run(['curl', '-s', url], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return None

def count_files(root, pattern):
    return len(list(Path(root).rglob(pattern)))

print("=" * 70)
print("COMPARATIVA BAGO: bago-framework (antiguo) vs BAGO (actual)")
print("=" * 70)
print()

# === REPO ANTIGUO ===
print("## 1. REPO ANTIGUO: MarcValls/bago-framework")
print()

old_commits = api_json("https://api.github.com/repos/MarcValls/bago-framework/commits?per_page=1&sha=main")
if old_commits:
    print(f"Ultimo commit: {old_commits[0]['commit']['author']['date']}")

old_tags = api_json("https://api.github.com/repos/MarcValls/bago-framework/tags")
if old_tags:
    print(f"Tags: {len(old_tags)}")
    for t in old_tags:
        print(f"  - {t['name']}")

old_releases = api_json("https://api.github.com/repos/MarcValls/bago-framework/releases")
print(f"Releases publicadas: {len(old_releases) if old_releases else 0}")

# README antiguo
old_readme = api_json("https://api.github.com/repos/MarcValls/bago-framework/readme")
if old_readme:
    print(f"README sha: {old_readme.get('sha', 'N/A')}")
    print(f"README size: {old_readme.get('size', 0)} bytes")

print()

# === REPO ACTUAL ===
print("## 2. REPO ACTUAL: MarcValls/BAGO")
print()

new_commits = api_json("https://api.github.com/repos/MarcValls/BAGO/commits?per_page=1")
if new_commits:
    print(f"Ultimo commit: {new_commits[0]['commit']['author']['date']}")

new_tags = api_json("https://api.github.com/repos/MarcValls/BAGO/tags")
if new_tags:
    print(f"Tags: {len(new_tags)}")
    for t in new_tags[:10]:
        print(f"  - {t['name']}")

new_releases = api_json("https://api.github.com/repos/MarcValls/BAGO/releases")
if new_releases:
    print(f"Releases publicadas: {len(new_releases)}")
    for r in new_releases:
        tag = r.get('tag_name', 'N/A')
        name = r.get('name', 'N/A')
        assets = len(r.get('assets', []))
        print(f"  - {tag}: {name} ({assets} assets)")

# README actual
new_readme = api_json("https://api.github.com/repos/MarcValls/BAGO/readme")
if new_readme:
    print(f"README sha: {new_readme.get('sha', 'N/A')}")
    print(f"README size: {new_readme.get('size', 0)} bytes")

print()

# === LOCAL BAGO ===
print("## 3. METRICAS LOCALES REPO BAGO (actual)")
print()

repo_root = Path("C:/Users/AMTEC_Terminal_1º/BAGO")

py_files = count_files(repo_root, "*.py")
md_files = count_files(repo_root, "*.md")
json_files = count_files(repo_root, "*.json")

print(f"Archivos Python (.py): {py_files}")
print(f"Archivos Markdown (.md): {md_files}")
print(f"Archivos JSON (.json): {json_files}")

# Contar comandos
sys.path.insert(0, str(repo_root / ".bago/tools"))
try:
    from tool_registry import REGISTRY
    core = sum(1 for e in REGISTRY.values() if e.stability == "core")
    dangerous = sum(1 for e in REGISTRY.values() if e.stability == "dangerous")
    experimental = sum(1 for e in REGISTRY.values() if e.stability == "experimental")
    legacy = sum(1 for e in REGISTRY.values() if e.stability == "legacy")
    print(f"Comandos registrados: {len(REGISTRY)}")
    print(f"  Core: {core}")
    print(f"  Dangerous: {dangerous}")
    print(f"  Experimental: {experimental}")
    print(f"  Legacy: {legacy}")
except Exception as e:
    print(f"Error cargando registry: {e}")

# Archivos en .bago/tools
bago_tools = list((repo_root / ".bago/tools").rglob("*.py"))
print(f"Tools en .bago/tools: {len(bago_tools)}")

# Workflows
workflows = list((repo_root / ".bago/workflows").rglob("*.md"))
print(f"Workflows documentados: {len(workflows)}")

# Docs
docs = list((repo_root / "docs").rglob("*.md"))
print(f"Docs en docs/: {len(docs)}")

print()
print("=" * 70)
print("FIN DEL REPORTE")
print("=" * 70)
