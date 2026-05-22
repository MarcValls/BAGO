#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import json
import multiprocessing as mp
import os
import random
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def percentile(values, p):
    if not values:
        return None
    arr = sorted(values)
    k = (len(arr) - 1) * p
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return arr[f]
    d0 = arr[f] * (c - k)
    d1 = arr[c] * (k - f)
    return d0 + d1


def resolve_bago_layout(base_path: Path):
    if (base_path / "roles").exists() and (base_path / "state").exists():
        return base_path.parent, base_path
    bago_dir = base_path / ".bago"
    if (bago_dir / "roles").exists() and (bago_dir / "state").exists():
        return base_path, bago_dir
    return base_path, bago_dir


def discover_roles(bago_dir: Path):
    roles_dir = bago_dir / "roles"
    if not roles_dir.exists():
        return []
    files = sorted(roles_dir.rglob("*.md"))
    roles = []
    for f in files:
        role = f.stem.strip().upper()
        if role:
            roles.append((role, str(f)))
    return roles


def build_prompt(role_name: str, role_path: str, prompt_size: int):
    base = (
        f"Eres el agente {role_name} de BAGO V2.2.2. "
        "Analiza consistencia canónica, riesgos de operación y salida accionable. "
        "Devuelve un resumen de 5 bullets con decisiones concretas."
    )
    filler = " Contexto crítico del repositorio y estado vivo." * max(1, prompt_size)
    return f"[ROLE_FILE={role_path}] {base}{filler}"


def post_json(url: str, payload: dict, headers: dict, timeout_s: int):
    if not url.startswith("https://"):
        raise ValueError(f"URL must use https scheme, got: {url!r}")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def call_openai(model: str, prompt: str, api_key: str, timeout_s: int, max_output_tokens: int):
    parsed = post_json(
        "https://api.openai.com/v1/responses",
        {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout_s=timeout_s,
    )
    usage = parsed.get("usage") or {}
    return {
        "ok": True,
        "error": "",
        "error_kind": "",
        "provider_status_code": "200",
        "attempts_made": 1,
        "retries_used": 0,
        "usage_input_tokens": usage.get("input_tokens"),
        "usage_output_tokens": usage.get("output_tokens"),
        "usage_total_tokens": usage.get("total_tokens"),
    }


def should_retry_github_models(status_code: str):
    return status_code in {"408", "429", "500", "502", "503", "504"}


def classify_error(error: str):
    if not error:
        return ""
    if error.startswith("github_models_http_"):
        return error.split(":", 1)[0]
    if error.startswith("http_"):
        return error
    if "timed out" in error.lower():
        return "timeout"
    if "curl_failed" in error:
        return "curl_failed"
    if "certificate verify failed" in error.lower():
        return "ssl_verify_failed"
    return "runtime_error"


def call_github_models(
    model: str,
    prompt: str,
    api_key: str,
    timeout_s: int,
    max_output_tokens: int,
    max_retries: int,
    backoff_base_ms: int,
    backoff_max_ms: int,
):
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
    )
    attempts = max(1, max_retries + 1)
    last_error = "github_models_unknown_error"
    last_status_code = ""
    for attempt in range(1, attempts + 1):
        cmd = [
            "curl",
            "-sS",
            "--max-time",
            str(timeout_s),
            "-X",
            "POST",
            "https://models.github.ai/inference/chat/completions",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            f"Authorization: Bearer {api_key}",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            "-H",
            "Content-Type: application/json",
            "-d",
            payload,
            "-w",
            "\n%{http_code}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            last_error = (result.stderr or "curl_failed").strip()[:200]
            if attempt >= attempts:
                return {
                    "ok": False,
                    "error": last_error,
                    "error_kind": classify_error(last_error),
                    "provider_status_code": last_status_code,
                    "attempts_made": attempt,
                    "retries_used": max(0, attempt - 1),
                    "usage_input_tokens": None,
                    "usage_output_tokens": None,
                    "usage_total_tokens": None,
                }
        else:
            body, _, status_code = result.stdout.rpartition("\n")
            status_code = status_code.strip()
            last_status_code = status_code
            if status_code == "200":
                parsed = json.loads(body)
                usage = parsed.get("usage") or {}
                return {
                    "ok": True,
                    "error": "",
                    "error_kind": "",
                    "provider_status_code": status_code,
                    "attempts_made": attempt,
                    "retries_used": max(0, attempt - 1),
                    "usage_input_tokens": usage.get("input_tokens"),
                    "usage_output_tokens": usage.get("output_tokens"),
                    "usage_total_tokens": usage.get("total_tokens"),
                }
            last_error = f"github_models_http_{status_code}: {body[:160]}"
            if not should_retry_github_models(status_code) or attempt >= attempts:
                return {
                    "ok": False,
                    "error": last_error,
                    "error_kind": classify_error(last_error),
                    "provider_status_code": status_code,
                    "attempts_made": attempt,
                    "retries_used": max(0, attempt - 1),
                    "usage_input_tokens": None,
                    "usage_output_tokens": None,
                    "usage_total_tokens": None,
                }

        sleep_ms = min(backoff_max_ms, backoff_base_ms * (2 ** (attempt - 1)))
        sleep_ms = max(50, int(sleep_ms * random.uniform(0.85, 1.15)))
        time.sleep(sleep_ms / 1000.0)

    return {
        "ok": False,
        "error": last_error,
        "error_kind": classify_error(last_error),
        "provider_status_code": last_status_code,
        "attempts_made": attempts,
        "retries_used": max(0, attempts - 1),
        "usage_input_tokens": None,
        "usage_output_tokens": None,
        "usage_total_tokens": None,
    }


def simulate_call(error_rate: float):
    latency = random.uniform(0.25, 1.6)
    time.sleep(latency)
    failed = random.random() < error_rate
    if failed:
        return {
            "ok": False,
            "error": "simulated_timeout",
            "error_kind": "simulated_timeout",
            "provider_status_code": "",
            "attempts_made": 1,
            "retries_used": 0,
            "usage_input_tokens": random.randint(200, 900),
            "usage_output_tokens": 0,
            "usage_total_tokens": None,
        }
    in_toks = random.randint(200, 1200)
    out_toks = random.randint(80, 500)
    return {
        "ok": True,
        "error": "",
        "error_kind": "",
        "provider_status_code": "",
        "attempts_made": 1,
        "retries_used": 0,
        "usage_input_tokens": in_toks,
        "usage_output_tokens": out_toks,
        "usage_total_tokens": in_toks + out_toks,
    }


def wait_global_rate_limit(rate_limit_rps: float, limiter_state, limiter_lock):
    if not rate_limit_rps or rate_limit_rps <= 0:
        return
    slot_s = 1.0 / rate_limit_rps
    while True:
        with limiter_lock:
            now = time.time()
            next_allowed = float(limiter_state.get("next_allowed_ts", 0.0) or 0.0)
            if now >= next_allowed:
                limiter_state["next_allowed_ts"] = now + slot_s
                return
            wait_s = next_allowed - now
        time.sleep(min(wait_s, 0.25))


def worker_proc(agent, role_path, cfg, status_map, out_q, limiter_state, limiter_lock):
    status_map[agent] = {
        "status": "idle",
        "iteration": 0,
        "completed": 0,
        "last_latency_ms": 0,
        "last_error": "",
        "pid": os.getpid(),
    }
    prompt = build_prompt(agent, role_path, cfg["prompt_size"])
    for i in range(1, cfg["iterations"] + 1):
        status_map[agent] = {
            **status_map[agent],
            "status": "running",
            "iteration": i,
        }
        t0 = time.time()
        if cfg["simulate"]:
            result = simulate_call(cfg["simulate_error_rate"])
        else:
            try:
                wait_global_rate_limit(
                    rate_limit_rps=cfg["global_rate_limit_rps"],
                    limiter_state=limiter_state,
                    limiter_lock=limiter_lock,
                )
                if cfg["provider"] == "github_models":
                    result = call_github_models(
                        model=cfg["model"],
                        prompt=prompt,
                        api_key=cfg["api_key"],
                        timeout_s=cfg["timeout_s"],
                        max_output_tokens=cfg["max_output_tokens"],
                        max_retries=cfg["github_max_retries"],
                        backoff_base_ms=cfg["github_backoff_base_ms"],
                        backoff_max_ms=cfg["github_backoff_max_ms"],
                    )
                else:
                    result = call_openai(
                        model=cfg["model"],
                        prompt=prompt,
                        api_key=cfg["api_key"],
                        timeout_s=cfg["timeout_s"],
                        max_output_tokens=cfg["max_output_tokens"],
                    )
            except urllib.error.HTTPError as e:
                result = {
                    "ok": False,
                    "error": f"http_{e.code}",
                    "error_kind": f"http_{e.code}",
                    "provider_status_code": str(e.code),
                    "attempts_made": 1,
                    "retries_used": 0,
                    "usage_input_tokens": None,
                    "usage_output_tokens": None,
                    "usage_total_tokens": None,
                }
            except Exception as e:  # noqa: BLE001
                result = {
                    "ok": False,
                    "error": str(e)[:200],
                    "error_kind": classify_error(str(e)[:200]),
                    "provider_status_code": "",
                    "attempts_made": 1,
                    "retries_used": 0,
                    "usage_input_tokens": None,
                    "usage_output_tokens": None,
                    "usage_total_tokens": None,
                }

        latency_ms = int((time.time() - t0) * 1000)
        out_q.put(
            {
                "timestamp_utc": utc_now(),
                "agent": agent,
                "iteration": i,
                "ok": result["ok"],
                "error": result["error"],
                "error_kind": result.get("error_kind", ""),
                "provider_status_code": result.get("provider_status_code", ""),
                "attempts_made": result.get("attempts_made", 1),
                "retries_used": result.get("retries_used", 0),
                "latency_ms": latency_ms,
                "input_tokens": result["usage_input_tokens"],
                "output_tokens": result["usage_output_tokens"],
                "total_tokens": result["usage_total_tokens"],
            }
        )
        status_map[agent] = {
            **status_map[agent],
            "status": "idle",
            "completed": i,
            "last_latency_ms": latency_ms,
            "last_error": result["error"],
        }
    status_map[agent] = {
        **status_map[agent],
        "status": "done",
    }


def pid_usage(pid: int):
    try:
        out = subprocess.check_output(["ps", "-p", str(pid), "-o", "%cpu=", "-o", "rss="], text=True).strip()
        if not out:
            return 0.0, 0
        parts = out.split()
        cpu = float(parts[0]) if parts else 0.0
        rss = int(parts[1]) if len(parts) > 1 else 0
        return cpu, rss
    except Exception:  # noqa: BLE001
        return 0.0, 0


def write_timeline(status_map, procs, timeline_path: Path, poll_s: float):
    fields = [
        "timestamp_utc",
        "agent",
        "status",
        "iteration",
        "completed",
        "last_latency_ms",
        "last_error",
        "pid",
        "pid_cpu_pct",
        "pid_rss_kb",
        "host_load_1m",
        "host_load_5m",
        "host_load_15m",
    ]
    with timeline_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        while True:
            alive = any(p.is_alive() for p in procs)
            snap_ts = utc_now()
            try:
                l1, l5, l15 = os.getloadavg()
            except OSError:
                l1, l5, l15 = 0.0, 0.0, 0.0

            snap = dict(status_map)
            for agent, st in snap.items():
                pid = int(st.get("pid", 0) or 0)
                cpu, rss = pid_usage(pid) if pid else (0.0, 0)
                writer.writerow(
                    {
                        "timestamp_utc": snap_ts,
                        "agent": agent,
                        "status": st.get("status", "unknown"),
                        "iteration": st.get("iteration", 0),
                        "completed": st.get("completed", 0),
                        "last_latency_ms": st.get("last_latency_ms", 0),
                        "last_error": st.get("last_error", ""),
                        "pid": pid,
                        "pid_cpu_pct": cpu,
                        "pid_rss_kb": rss,
                        "host_load_1m": round(l1, 3),
                        "host_load_5m": round(l5, 3),
                        "host_load_15m": round(l15, 3),
                    }
                )
            f.flush()
            if not alive:
                break
            time.sleep(poll_s)


def summarize(results, cfg):
    lat = [r["latency_ms"] for r in results]
    oks = sum(1 for r in results if r["ok"])
    errs = len(results) - oks
    total_retries = sum(int(r.get("retries_used", 0) or 0) for r in results)
    recovered_after_retry = sum(
        1 for r in results if r["ok"] and int(r.get("retries_used", 0) or 0) > 0
    )
    error_breakdown = {}
    for r in results:
        key = r.get("error_kind", "") or "none"
        error_breakdown[key] = error_breakdown.get(key, 0) + 1
    by_agent = {}
    for r in results:
        a = r["agent"]
        by_agent.setdefault(a, []).append(r)

    ag = {}
    for a, rows in by_agent.items():
        al = [x["latency_ms"] for x in rows]
        ag[a] = {
            "requests": len(rows),
            "ok": sum(1 for x in rows if x["ok"]),
            "errors": sum(1 for x in rows if not x["ok"]),
            "retries_used_total": sum(int(x.get("retries_used", 0) or 0) for x in rows),
            "latency_ms_avg": round(statistics.mean(al), 2) if al else None,
            "latency_ms_p95": round(percentile(al, 0.95), 2) if al else None,
        }

    duration_s = cfg["ended_at_ts"] - cfg["started_at_ts"]
    throughput_windows = []
    if results:
        base_ts = min(dt.datetime.fromisoformat(r["timestamp_utc"]) for r in results)
        bucket = {}
        for r in results:
            sec = int((dt.datetime.fromisoformat(r["timestamp_utc"]) - base_ts).total_seconds())
            window = (sec // 10) * 10
            bucket[window] = bucket.get(window, 0) + 1
        throughput_windows = [
            {"second_from_start": sec, "requests": count, "rps_avg": round(count / 10.0, 3)}
            for sec, count in sorted(bucket.items())
        ]
    return {
        "started_at_utc": cfg["started_at_utc"],
        "ended_at_utc": cfg["ended_at_utc"],
        "duration_s": round(duration_s, 3),
        "simulate": cfg["simulate"],
        "provider": cfg["provider"],
        "model": cfg["model"],
        "agents": cfg["agents"],
        "iterations_per_agent": cfg["iterations"],
        "global_rate_limit_rps": cfg["global_rate_limit_rps"],
        "total_requests": len(results),
        "ok_requests": oks,
        "error_requests": errs,
        "error_rate": round(errs / len(results), 4) if results else 0.0,
        "throughput_rps": round(len(results) / duration_s, 3) if duration_s > 0 else 0.0,
        "latency_ms_avg": round(statistics.mean(lat), 2) if lat else None,
        "latency_ms_p50": round(percentile(lat, 0.50), 2) if lat else None,
        "latency_ms_p95": round(percentile(lat, 0.95), 2) if lat else None,
        "latency_ms_p99": round(percentile(lat, 0.99), 2) if lat else None,
        "error_breakdown": error_breakdown,
        "retry_summary": {
            "total_retries_used": total_retries,
            "requests_recovered_after_retry": recovered_after_retry,
            "retry_rate_over_requests": round(total_retries / len(results), 4) if results else 0.0,
        },
        "throughput_windows_10s": throughput_windows,
        "by_agent": ag,
    }


def parse_args():
    p = argparse.ArgumentParser(description="Stress test de agentes BAGO aislados")
    p.add_argument(
        "--bago-root",
        default=".",
        help="Raíz del repo o carpeta .bago",
    )
    p.add_argument("--agents", type=int, default=8, help="Cantidad de agentes")
    p.add_argument("--iterations", type=int, default=25, help="Iteraciones por agente")
    p.add_argument(
        "--provider",
        choices=("openai", "github_models"),
        default="openai",
        help="Backend de inferencia",
    )
    p.add_argument("--model", default="gpt-5.4-mini", help="Modelo a estresar")
    p.add_argument("--timeout-s", type=int, default=90)
    p.add_argument("--max-output-tokens", type=int, default=400)
    p.add_argument("--prompt-size", type=int, default=40, help="Tamaño de prompt sintético")
    p.add_argument("--poll-s", type=float, default=1.0, help="Frecuencia observador")
    p.add_argument("--global-rate-limit-rps", type=float, default=0.0, help="Límite global opcional de requests por segundo")
    p.add_argument("--github-max-retries", type=int, default=3, help="Reintentos ante 429/5xx en GitHub Models")
    p.add_argument("--github-backoff-base-ms", type=int, default=750, help="Backoff base en ms para GitHub Models")
    p.add_argument("--github-backoff-max-ms", type=int, default=8000, help="Backoff máximo en ms para GitHub Models")
    p.add_argument("--simulate", action="store_true", help="No llama API; simula latencia/errores")
    p.add_argument("--simulate-error-rate", type=float, default=0.03)
    p.add_argument(
        "--runs-dir",
        default=".bago/state/metrics/runs",
        help="Directorio base para resultados",
    )
    return p.parse_args()


def resolve_api_key(provider: str):
    if provider == "github_models":
        return os.environ.get("GITHUB_MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    return os.environ.get("OPENAI_API_KEY", "")


def main():
    args = parse_args()
    root = Path(args.bago_root).resolve()
    repo_root, bago_dir = resolve_bago_layout(root)
    runs_dir = (repo_root / args.runs_dir).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = runs_dir / f"stress_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    roles = discover_roles(bago_dir)
    if not roles:
        print(f"No se encontraron roles en {bago_dir / 'roles'}", file=sys.stderr)
        return 2

    needed = max(1, args.agents)
    role_cycle = [roles[i % len(roles)] for i in range(needed)]

    api_key = resolve_api_key(args.provider)
    simulate = args.simulate or not api_key
    if not simulate and not api_key:
        if args.provider == "github_models":
            print("GITHUB_MODELS_TOKEN o GITHUB_TOKEN no disponible", file=sys.stderr)
        else:
            print("OPENAI_API_KEY no disponible", file=sys.stderr)
        return 2

    manager = mp.Manager()
    status_map = manager.dict()
    out_q = manager.Queue()
    limiter_state = manager.dict({"next_allowed_ts": 0.0})
    limiter_lock = manager.RLock()

    cfg = {
        "iterations": max(1, args.iterations),
        "provider": args.provider,
        "model": args.model,
        "timeout_s": max(5, args.timeout_s),
        "max_output_tokens": max(1, args.max_output_tokens),
        "prompt_size": max(1, args.prompt_size),
        "global_rate_limit_rps": max(0.0, args.global_rate_limit_rps),
        "github_max_retries": max(0, args.github_max_retries),
        "github_backoff_base_ms": max(50, args.github_backoff_base_ms),
        "github_backoff_max_ms": max(100, args.github_backoff_max_ms),
        "simulate": simulate,
        "simulate_error_rate": max(0.0, min(args.simulate_error_rate, 0.9)),
        "api_key": api_key,
        "agents": needed,
    }

    started = time.time()
    cfg["started_at_ts"] = started
    cfg["started_at_utc"] = utc_now()

    processes = []
    for i, (role_name, role_path) in enumerate(role_cycle, start=1):
        agent = f"AGENTE_{i:02d}_{role_name}"
        p = mp.Process(
            target=worker_proc,
            args=(agent, role_path, cfg, status_map, out_q, limiter_state, limiter_lock),
            daemon=False,
        )
        processes.append(p)
        p.start()

    timeline_path = run_dir / "agent_timeline.csv"
    write_timeline(status_map=status_map, procs=processes, timeline_path=timeline_path, poll_s=max(0.2, args.poll_s))

    for p in processes:
        p.join()

    results = []
    while not out_q.empty():
        results.append(out_q.get())

    ended = time.time()
    cfg["ended_at_ts"] = ended
    cfg["ended_at_utc"] = utc_now()

    results.sort(key=lambda x: (x["timestamp_utc"], x["agent"], x["iteration"]))

    results_csv = run_dir / "results.csv"
    with results_csv.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "timestamp_utc",
            "agent",
            "iteration",
            "ok",
            "error",
            "error_kind",
            "provider_status_code",
            "attempts_made",
            "retries_used",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(results)

    summary = summarize(results, cfg)
    summary_json = run_dir / "summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    run_info = {
        "run_dir": str(run_dir),
        "simulate": simulate,
        "provider": args.provider,
        "model": args.model,
        "agents": needed,
        "iterations": args.iterations,
        "global_rate_limit_rps": max(0.0, args.global_rate_limit_rps),
        "generated_files": [
            str(results_csv),
            str(timeline_path),
            str(summary_json),
        ],
    }
    (run_dir / "run_info.json").write_text(json.dumps(run_info, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(run_info, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
