"""Patch _handle_chat to resolve provider/model and pass them to print_message_qwen."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
text = P.read_text(encoding="utf-8")

# Find the function body boundaries.
start_marker = '    def _handle_chat(self, text: str) -> None:'
start = text.find(start_marker)
assert start >= 0, "_handle_chat not found"

# End of function: next "    def " at column 4 with "self" parameter,
# or end of class. We just take until the next occurrence of "    def _prompt".
end = text.find("    def _prompt(self)", start)
assert end > start, "_prompt not found after _handle_chat"

old_block = text[start:end]
new_block = '''    def _handle_chat(self, text: str) -> None:
        """Env\u00eda mensaje al LLM y muestra respuesta dentro de la burbuja BAGO."""
        if _is_transcript(text):
            print(R.warn(
                "\u26a0 Transcript detectado \u2014 tratando el bloque como contexto no ejecutable."
            ))
            text = _wrap_transcript(text)
        # Resolve active provider/model so the assistant bubble can show which engine answers.
        provider = ""
        model = ""
        try:
            mgr = getattr(self, "mgr", None)
            if mgr is not None:
                for source in (
                    mgr,
                    getattr(mgr, "session", None),
                    getattr(mgr, "_adapter", None),
                ):
                    if source is None:
                        continue
                    provider = provider or getattr(source, "provider", "") or ""
                    model = model or getattr(source, "model", "") or ""
        except Exception:
            pass
        try:
            if self.mgr.config.feature_streaming and self.mgr._adapter and self.mgr._adapter.supports_streaming():
                spinner_frames = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c", "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]
                idx = 0
                sys.stdout.write(R.dim(f"{spinner_frames[0]} pensando\u2026"))
                sys.stdout.flush()
                chunks: list[str] = []
                for chunk in self.mgr.send_stream(text):
                    if idx == 0:
                        sys.stdout.write("\r" + " " * 20 + "\r")
                        sys.stdout.flush()
                    chunks.append(chunk)
                    idx += 1
                    if idx % 3 == 0:
                        sys.stdout.write("\r" + R.dim(f"{spinner_frames[(idx // 3) % len(spinner_frames)]} pensando\u2026"))
                        sys.stdout.flush()
                sys.stdout.write("\r" + " " * 20 + "\r")
                sys.stdout.flush()
                full = "".join(chunks).strip()
                if full:
                    R.print_message_qwen("assistant", full, state="received", provider=provider, model=model)
                else:
                    print(R.dim("(sin respuesta)"))
            else:
                response = self.mgr.send(text)
                R.print_message_qwen("assistant", response or "(sin respuesta)", state="received", provider=provider, model=model)
        except Exception as exc:
            print(R.error(f"Error de provider: {exc}"))

'''

text = text[:start] + new_block + text[end:]
P.write_text(text, encoding="utf-8")
print("patched")