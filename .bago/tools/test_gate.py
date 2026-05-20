import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def main():
    args = sys.argv[1:]
    cmd = [sys.executable, "-m", "pytest"] + (args if args else ["-q"])
    print(f"  running: {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=str(ROOT))
    return r.returncode

if __name__ == "__main__":
    sys.exit(main())