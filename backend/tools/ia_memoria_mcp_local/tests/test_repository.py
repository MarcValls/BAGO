from pathlib import Path
from ia_memoria.config import Settings
from ia_memoria.repository import MemoryRepository

def settings(root: Path)->Settings:
    return Settings(root,"stdio","127.0.0.1",8765,524288,20,frozenset({".md",".txt",".json",".jsonl",".yaml",".yml",".toml"}))

def test_propose_commit_search(tmp_path: Path):
    r=MemoryRepository(settings(tmp_path)); r.initialize(); r.create_project("TEST","Prueba","Validar persistencia.")
    p=r.propose_memory("TEST","La salida debe verificarse.","regla","test",proposed_class="MEM_CONFIRMED")
    c=r.commit_memory(p["proposal_id"],"tester"); result=r.search("verificarse","TEST")
    assert c["status"]=="active" and result["memories"][0]["statement"]=="La salida debe verificarse."

def test_read_boundary(tmp_path: Path):
    r=MemoryRepository(settings(tmp_path)); r.initialize(); r.create_project("TEST","Prueba","Validar lectura.")
    assert "Proyecto: TEST" in r.read_file("20_PROJECTS/TEST/00_IDENTIDAD_Y_ALCANCE.md")["content"]
