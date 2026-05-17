#!/usr/bin/env python3
"""bago_copilot_bridge.py — Lanza GitHub Copilot desde CLI via web o VS Code."""
import sys
import subprocess
import webbrowser
from pathlib import Path

def find_vscode():
    for p in [
        Path.home() / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
        Path("C:/Program Files/Microsoft VS Code/bin/code.cmd"),
        Path("C:/Program Files (x86)/Microsoft VS Code/bin/code.cmd"),
    ]:
        if p.exists():
            return str(p)
    # Try PATH
    try:
        r = subprocess.run(["where.exe", "code"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None

def launch_copilot(model="claude-sonnet-4.6", task=""):
    vscode = find_vscode()
    if vscode:
        # Try to open Copilot Chat in VS Code
        try:
            subprocess.Popen([vscode, "--command", "github.copilot.chat.new"], shell=False)
            print(f"[BAGO] VS Code Copilot Chat abierto (modelo: {model})")
            return 0
        except Exception as e:
            print(f"[BAGO] VS Code falló: {e}")
    
    # Fallback: open GitHub Copilot web chat
    url = "https://github.com/copilot"
    if task:
        # GitHub Copilot Chat doesn't have URL params for tasks, but we can open the chat
        url = "https://github.com/copilot/chat"
    
    webbrowser.open(url)
    print(f"[BAGO] GitHub Copilot web abierto: {url}")
    print(f"[BAGO] Modelo solicitado: {model}")
    print("[BAGO] Nota: Para uso CLI nativo, instala 'gh' + extension 'gh-copilot'")
    return 0

if __name__ == "__main__":
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-sonnet-4.6"
    task = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
    sys.exit(launch_copilot(model, task))
