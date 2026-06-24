"""trace_boot.py — wrap stdout.write to track which function prints what."""
import os, sys, io, functools

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
sys.path.insert(0, r"bago_core")

for k in list(sys.modules.keys()):
    if k in ("repl", "repl_banner", "repl_status", "repl_navigation",
             "repl_prompt", "repl_chat", "repl_autoload",
             "repl_layout", "repl_intent", "renderer", "version",
             "commands", "session_manager", "switch_engine",
             "session_provider", "state_paths", "system_prompt",
             "intent_engine", "intent_examples"):
        del sys.modules[k]

# Trace stdout writes
trace_log = []
real_stdout = sys.stdout


class TracingStdout:
    def __init__(self, real):
        self._real = real
        self._line_buf = ""

    def write(self, s):
        self._line_buf += s
        while "\n" in self._line_buf:
            line, self._line_buf = self._line_buf.split("\n", 1)
            if line.strip():
                # Find which frame in call stack is in our code
                import inspect
                for frame_info in inspect.stack()[1:6]:
                    fn = frame_info.function
                    mod = frame_info.filename
                    if "/BAGO/" in mod and "trace_boot" not in mod:
                        trace_log.append(f"[{fn:25}] {line[:80]}")
                        break
                else:
                    trace_log.append(f"[<unknown>]              {line[:80]}")
        return self._real.write(s)

    def flush(self):
        return self._real.flush()

    def __getattr__(self, name):
        return getattr(self._real, name)


sys.stdout = TracingStdout(real_stdout)
sys.stderr = TracingStdout(real_stdout)

from repl import BagoREPL
import session_manager as sm_mod
import switch_engine as se_mod

repl = BagoREPL(
    provider="ollama-local",
    model="llama3.2:3b",
    system_prompt="",
    base_path=os.getcwd(),
)

# Run the full boot path
repl._setup_readline()
repl._print_banner()
repl._print_status()
repl._print_init_warnings()
repl._auto_evolve_startup()
# Skip prompt so we don't hang

sys.stdout = real_stdout
sys.stderr = real_stdout

print("=" * 70)
print("TRACE: who printed what during boot")
print("=" * 70)
for entry in trace_log:
    print(entry)
