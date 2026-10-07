from __future__ import annotations
import json,sys
from .config import Settings
from .repository import MemoryRepository

def repo(): return MemoryRepository(Settings.from_env())
def init_main(): print(json.dumps(repo().initialize(),ensure_ascii=False,indent=2))
def doctor_main():
    try:
        r=repo(); result=r.system_status(); result['projects']=r.list_projects(); result['python']=sys.version.split()[0]; print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e: print(f"ERROR: {type(e).__name__}: {e}",file=sys.stderr); raise SystemExit(1)
def reindex_main():
    r=repo(); r.initialize(); print(json.dumps(r.reindex(),ensure_ascii=False,indent=2))
def backup_main():
    r=repo(); r.initialize(); print(r.backup())
if __name__=='__main__': doctor_main()
