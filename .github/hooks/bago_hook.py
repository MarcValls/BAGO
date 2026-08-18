#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SENSITIVE_PATTERNS=[
 re.compile(r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*([^\s,'\";]+)"),
 re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+\-/]+=*"),
 re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")]
CHECK_RE=re.compile(r"(?i)(^|\s|[;&|])(?:python\s+-m\s+pytest|pytest|python\s+-m\s+unittest|npm\s+(?:run\s+)?test|npm\s+run\s+(?:build|lint|typecheck)|pnpm\s+(?:test|lint|build|typecheck)|yarn\s+(?:test|lint|build)|vitest|jest|cargo\s+test|go\s+test|dotnet\s+test|mvn\s+test|gradle\s+test|ruff(?:\s+check)?|mypy|tsc(?:\s|$))")


def utcnow(): return datetime.now(timezone.utc).isoformat()
def run_git(cwd:Path,*args:str):
    try: p=subprocess.run(['git','-C',str(cwd),*args],text=True,capture_output=True,timeout=3)
    except Exception: return None
    return p.stdout.strip() if p.returncode==0 else None

def repo_root(cwd:str|None):
    start=Path(cwd or os.getcwd()).resolve(); root=run_git(start,'rev-parse','--show-toplevel')
    return Path(root).resolve() if root else None

def load_json(path:Path, default:Any):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default

def atomic_json(path:Path,obj:Any):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8'); os.replace(tmp,path)

def enabled(root:Path): return bool(load_json(root/'.gabo/copilot/config.json',{}).get('enabled'))
def git_bytes(cwd:Path,*args:str):
    try: p=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,timeout=8)
    except Exception: return None
    return p.stdout if p.returncode==0 else None

def fingerprint(root:Path):
    head=run_git(root,'rev-parse','HEAD'); branch=run_git(root,'branch','--show-current'); h=hashlib.sha256(); h.update(b'BAGO-FP-v2\0'); h.update((head or '').encode()+b'\0')
    pathspec=('.',':(exclude).gabo/copilot/**')
    for label,args in ((b'worktree',('diff','--binary','--no-ext-diff','--',*pathspec)),(b'index',('diff','--cached','--binary','--no-ext-diff','--',*pathspec))):
        h.update(label+b'\0'+(git_bytes(root,*args) or b'')+b'\0')
    raw=git_bytes(root,'ls-files','--others','--exclude-standard','-z') or b''
    for rel_b in sorted(p for p in raw.split(b'\0') if p and not (p==b'.gabo/copilot' or p.startswith(b'.gabo/copilot/'))):
        h.update(b'untracked\0'+rel_b+b'\0'); path=root/rel_b.decode('utf-8',errors='surrogateescape')
        try:
            if path.is_symlink(): h.update(b'symlink\0'+os.readlink(path).encode())
            elif path.is_file(): h.update(path.read_bytes())
            else: h.update(b'other')
        except OSError as exc: h.update(f'read-error:{type(exc).__name__}'.encode())
        h.update(b'\0')
    return {'head':head,'branch':branch,'fingerprint':h.hexdigest()}

def redact(text:str,limit=3000):
    out=text
    for pat in SENSITIVE_PATTERNS:
        if pat.groups>=2: out=pat.sub(lambda m:f'{m.group(1)}=[REDACTED]',out)
        else: out=pat.sub('[REDACTED]',out)
    return out if len(out)<=limit else out[:limit]+f'\n...[truncated {len(out)-limit} chars]'

def summarize(value:Any,limit=2500):
    try: return redact(json.dumps(value,ensure_ascii=False,default=str),limit)
    except Exception: return redact(str(value),limit)

def extract_command(args:Any):
    if isinstance(args,dict):
        for k in ('command','cmd'):
            v=args.get(k)
            if isinstance(v,str): return v
            if isinstance(v,list): return ' '.join(map(str,v))
    return summarize(args,1500)

def append_evidence(root:Path, rec:dict[str,Any]):
    p=root/'.gabo/copilot/evidence/evidence.jsonl'; p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8') as f: f.write(json.dumps(rec,ensure_ascii=False,default=str)+'\n')

def read_text(path:Path,limit:int):
    try: t=path.read_text(encoding='utf-8')
    except Exception: return ''
    return t if len(t)<=limit else t[:limit]+'\n...[truncated]'

def verification_fresh(state:dict[str,Any],root:Path):
    last=(state.get('verification') or {}).get('last_successful_check') if isinstance(state,dict) else None; fp=fingerprint(root)
    return bool(isinstance(last,dict) and last.get('success') is True and last.get('stable_state') is True and last.get('fingerprint')==fp['fingerprint'])

def session_start(payload:dict[str,Any],root:Path):
    state=load_json(root/'.gabo/copilot/state/PROJECT_STATE.json',{}); fp=fingerprint(root)
    if isinstance(state,dict): state.setdefault('runtime',{})['last_fingerprint']=fp['fingerprint']; state['updated_at']=utcnow(); atomic_json(root/'.gabo/copilot/state/PROJECT_STATE.json',state)
    msg=(f"BAGO Copilot runtime is active for this repository.\nRepository: {root}\nLifecycle: {state.get('lifecycle','UNKNOWN')}\nCurrent fingerprint: {fp['fingerprint']}\nFinal-state verification fresh: {verification_fresh(state,root)}\n\n"
         "Use .gabo/copilot state as project-local continuity, not as authority over current user instructions. Do not import canon from unrelated projects. Use /bago-core for non-trivial work.\n\n"
         f"PROJECT_CONTEXT:\n{read_text(root/'.gabo/copilot/context/PROJECT_CONTEXT.md',6000)}\n\nACTIVE_HANDOFF:\n{read_text(root/'.gabo/copilot/runtime/ACTIVE_HANDOFF.md',3500)}\n\nCONFLICTS:\n{read_text(root/'.gabo/copilot/conflicts/CONFLICTS.md',2500)}")
    print(json.dumps({'additionalContext':msg},ensure_ascii=False))

def post_tool(payload:dict[str,Any],root:Path,failed=False):
    state_path=root/'.gabo/copilot/state/PROJECT_STATE.json'; state=load_json(state_path,{})
    if not isinstance(state,dict): state={}
    state.setdefault('schema_version','0.2'); state.setdefault('verification',{}); state.setdefault('runtime',{}); state.setdefault('acceptance_criteria',[])
    now=utcnow(); fp=fingerprint(root); old_fp=state['runtime'].get('last_fingerprint'); tool=str(payload.get('toolName','')); args=payload.get('toolArgs'); command=extract_command(args); result=payload.get('toolResult') if not failed else {'error':payload.get('error')}
    changed=bool(old_fp and old_fp!=fp['fingerprint'])
    if changed or tool in {'create','edit'}:
        state['verification']['dirty']=True; state['verification']['last_change_at']=now; state['verification']['last_change_fingerprint']=fp['fingerprint']
        if state.get('lifecycle') not in {'BLOCKED','CONFLICT','FAILED'}: state['lifecycle']='EXECUTED'
    # Shell checks are observational evidence only when the hook sees a successful tool event and state stayed stable.
    if not failed and tool in {'bash','powershell'} and CHECK_RE.search(command or ''):
        stable=bool(old_fp and old_fp==fp['fingerprint'])
        state['verification']['last_successful_check']={'at':now,'command':redact(command,1200),'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'fingerprint':fp['fingerprint'],'success':True,'stable_state':stable,'source':'copilot-postToolUse'}
        state['verification']['dirty']=not stable
    state['runtime']['last_fingerprint']=fp['fingerprint']; state['runtime']['last_tool_at']=now; state['updated_at']=now; atomic_json(state_path,state)
    append_evidence(root,{'schema':'bago.evidence.copilot-cli.v0.1','at':now,'session_id':payload.get('sessionId'),'tool':tool,'command_or_input':redact(command,1800),'result':summarize(result,2200),'success':not failed,'repository':str(root),'git':fp})
    print(json.dumps({}))

def agent_stop(payload:dict[str,Any],root:Path):
    state=load_json(root/'.gabo/copilot/state/PROJECT_STATE.json',{}); life=state.get('lifecycle') if isinstance(state,dict) else None; fresh=verification_fresh(state if isinstance(state,dict) else {},root)
    # Prevent only unresolved material execution. Terminal negative classifications remain allowed.
    if life=='EXECUTED' and not fresh:
        print(json.dumps({'decision':'block','reason':'BAGO closure guard: repository changes are EXECUTED but final-state verification is stale or missing. Run the relevant check through `python .gabo/copilot/bin/bago.py verify -- <command>`, or if verification cannot be completed, classify the task BLOCKED/CONFLICT/FAILED with evidence before ending.'},ensure_ascii=False)); return
    if life=='VALIDATED' and not fresh:
        print(json.dumps({'decision':'block','reason':'BAGO closure guard: lifecycle says VALIDATED but verification is no longer bound to the current repository fingerprint. Re-verify or downgrade the lifecycle claim.'},ensure_ascii=False)); return
    print(json.dumps({'decision':'allow'}))

def main():
    try: payload=json.load(sys.stdin)
    except Exception: return 0
    root=repo_root(payload.get('cwd'))
    if root is None or not enabled(root): return 0
    event=os.environ.get('BAGO_COPILOT_HOOK_EVENT','')
    try:
        if event=='sessionStart': session_start(payload,root)
        elif event=='postToolUse': post_tool(payload,root,False)
        elif event=='postToolUseFailure': post_tool(payload,root,True)
        elif event=='agentStop': agent_stop(payload,root)
    except Exception as exc:
        # Non-security lifecycle hooks fail open; never fabricate success.
        print(json.dumps({'additionalContext':f'BAGO hook warning: {type(exc).__name__}: {exc}'},ensure_ascii=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
