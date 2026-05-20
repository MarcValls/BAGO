import subprocess, sys, json, time
sys.path.insert(0, '.bago/tools')
from tool_registry import REGISTRY

results = {}
for cmd, entry in sorted(REGISTRY.items()):
    start = time.time()
    ec = None
    out = ""
    err = ""
    for arg in [['--help'], ['--preflight'], []]:
        try:
            proc = subprocess.run([sys.executable, 'bago', cmd] + arg, capture_output=True, text=True, timeout=8)
            ec = proc.returncode
            out = proc.stdout[:300]
            err = proc.stderr[:300]
            if ec == 0:
                break
        except subprocess.TimeoutExpired:
            ec = -1
            out = "TIMEOUT"
        except Exception as e:
            ec = -2
            err = str(e)[:300]
    results[cmd] = {
        'code': ec if ec is not None else -3,
        'time': round(time.time()-start,2),
        'stability': entry.stability,
        'module': entry.module,
        'out_snip': out,
        'err_snip': err
    }
    print(f"OK {cmd}", flush=True)

with open('cmd_test_results.json','w',encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("DONE")
