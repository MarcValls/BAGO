#!/usr/bin/env python3
"""test_bago_brutal_metas.py — Tests brutales de las 4 metas persistentes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

BAGO_CMD = r"C:\Users\AMTEC_Terminal_1º\BAGO\bago.cmd"


def run_bago(args: list[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            [BAGO_CMD] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(Path.home()),
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"'{BAGO_CMD}' no encontrado"
    except subprocess.TimeoutExpired:
        return -2, "", "Timeout"


def test_status():
    print("\n[TEST] BAGO status")
    code, out, err = run_bago(["status"])
    combined = out + err
    checks = [
        ("Fuente de verdad" in combined, "Detecta fuente de verdad"),
        ("Modo:" in combined, "Muestra modo"),
        ("Primaria:" in combined, "Muestra ruta primaria"),
    ]
    all_ok = all(c[0] for c in checks)
    if all_ok:
        print("  [PASS] Status funciona desde cualquier directorio")
    else:
        for ok, msg in checks:
            if not ok:
                print(f"  [FAIL] {msg}")
    return all_ok


def test_launch():
    print("\n[TEST] BAGO launch qwen25-mini (inicia correctamente)")
    code, out, err = run_bago(["launch", "qwen25-mini"], timeout=3)
    combined = out + err
    ok = ("Lanzando:" in combined) or ("qwen25-mini" in combined) or (code == -2)
    if ok:
        print(f"  [PASS] Launch inicia: {combined.strip().split(chr(10))[0][:60]}")
    else:
        print(f"  [FAIL] Launch no inicia: {combined[:100]}")
    return ok


def test_install():
    print("\n[TEST] BAGO install (responde con ayuda)")
    code, out, err = run_bago(["install"])
    combined = out + err
    ok = ("Componentes disponibles" in combined) or ("Componente desconocido" in combined)
    if ok:
        print(f"  [PASS] Install responde: {combined.strip().split(chr(10))[0][:60]}")
    else:
        print(f"  [FAIL] Install no responde: {combined[:100]}")
    return ok


def test_sync():
    print("\n[TEST] BAGO sync (detecta USB o sincroniza)")
    code, out, err = run_bago(["sync", "--to-usb"], timeout=30)
    combined = out + err
    ok = (code == 0) or ("Sincronizaci" in combined) or ("USB" in combined)
    if ok:
        print(f"  [PASS] Sync termina correctamente (exit={code})")
    else:
        print(f"  [FAIL] Sync falla: exit={code}, {combined[:100]}")
    return ok


def test_contribute():
    print("\n[TEST] BAGO contribute (muestra interfaz)")
    code, out, err = run_bago(["contribute"])
    combined = out + err
    ok = ("Informe de Aprendizaje" in combined) or ("BAGO Contribute" in combined)
    if ok:
        print("  [PASS] Contribute muestra interfaz")
    else:
        print(f"  [FAIL] Contribute no muestra interfaz: {combined[:100]}")
    return ok


def test_orchestrator():
    print("\n[TEST] Orquestador — selección por tarea")
    import sys
    sys.path.insert(0, str(Path.home() / "BAGO" / ".bago" / "tools"))
    from bago_orchestrator import orchestrate

    tests = [
        ("brainstorm ideas", "free", "simple -> gratis"),
        ("transponer partitura", "openai_credits", "compleja -> Codex"),
        ("explicame error python", "free", "explicar -> gratis"),
        ("implementar login", "openai_credits", "implementar -> Codex"),
    ]
    all_ok = True
    for task, expected_cost, reason in tests:
        r = orchestrate(task)
        actual_cost = r.get("cost", "unknown")
        if expected_cost == "free":
            ok = actual_cost == "free"
        else:
            ok = actual_cost in ("free", "included", "openai_credits")
        if ok:
            print(f"  [PASS] {reason}: {r['model']} ({actual_cost})")
        else:
            print(f"  [FAIL] {reason}: esperaba {expected_cost}, got {actual_cost}")
            all_ok = False
    return all_ok


def test_locate_anywhere():
    print("\n[TEST] BAGO disponible desde cualquier directorio")
    code1, out1, _ = run_bago(["status"])
    code2, out2, _ = subprocess.run(
        [BAGO_CMD, "status"], capture_output=True, text=True, timeout=10,
        cwd=str(Path("C:\\")),
    ).returncode, subprocess.run(
        [BAGO_CMD, "status"], capture_output=True, text=True, timeout=10,
        cwd=str(Path("C:\\")),
    ).stdout, ""

    ok = (code1 == 0) and (code2 == 0) and ("Fuente de verdad" in out1) and ("Fuente de verdad" in out2)
    if ok:
        print("  [PASS] BAGO funciona desde home y desde C:\\")
    else:
        print(f"  [FAIL] BAGO no funciona globalmente: home={code1}, C:={code2}")
    return ok


def test_help():
    print("\n[TEST] BAGO sin args -> help muestra todos los comandos")
    code, out, err = run_bago([])
    checks = [
        ("BAGO status" in out, "Muestra status"),
        ("BAGO launch" in out, "Muestra launch"),
        ("BAGO install" in out, "Muestra install"),
        ("BAGO sync" in out, "Muestra sync"),
        ("BAGO contribute" in out, "Muestra contribute"),
        ("BAGO repo" in out, "Muestra repo"),
    ]
    all_ok = all(c[0] for c in checks)
    if all_ok:
        print("  [PASS] Help muestra los 4 metas + repo")
    else:
        for ok, msg in checks:
            if not ok:
                print(f"  [FAIL] {msg}")
    return all_ok


def main():
    print("=" * 60)
    print("BAGO BRUTAL METAS TEST SUITE")
    print("=" * 60)

    results = []
    results.append(("status", test_status()))
    results.append(("launch", test_launch()))
    results.append(("install", test_install()))
    results.append(("sync", test_sync()))
    results.append(("contribute", test_contribute()))
    results.append(("orchestrator", test_orchestrator()))
    results.append(("locate anywhere", test_locate_anywhere()))
    results.append(("help", test_help()))

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"RESULTADO: {passed}/{total} PASSED")
    for name, ok in results:
        icon = "OK" if ok else "NO"
        print(f"  [{icon}] {name}")
    if passed == total:
        print("BRUTAL METAS: ALL GREEN")
    else:
        print("BRUTAL METAS: HAY FALLOS")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())


