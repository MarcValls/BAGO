"""Rewrite the entire _handle_chat body cleanly. No regex heuristics."""
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl.py")
text = P.read_text(encoding="utf-8")

start = text.find("    def _handle_chat(self, text: str) -> None:")
assert start >= 0
end = text.find("    def _prompt(self)", start)
assert end > start

new_body = '''    def _handle_chat(self, text: str) -> None:
        """Send a message to the LLM and render the reply inside the BAGO bubble."""
        from .repl_chat import handle_chat
        handle_chat(self, text)


'''

text = text[:start] + new_body + text[end:]
P.write_text(text, encoding="utf-8")
print("wrote stub _handle_chat that delegates to repl_chat.handle_chat")