"""Smoke test for repl_layout.SplitLayout.

Renders a fake chat session to verify the header sticks to the top and
the prompt sticks to the bottom while the middle scrolls.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
from repl_layout import SplitLayout


def main():
    layout = SplitLayout(header_lines=2)
    layout.enter()
    layout.header([
        "\x1b[36mBAGO v4.7.0\x1b[0m  \x1b[2m| provider: ollama-local | llama3.2:3b\x1b[0m",
        "\x1b[2m" + ("-" * 80) + "\x1b[0m",
    ])

    # Simulate a few chat turns. Each turn scrolls the middle zone.
    for i in range(3):
        layout.print_below(f"\x1b[2m\u276f user:\x1b[0m  mensaje {i}\n")
        layout.print_below(f"\x1b[36m\u276f BAGO:\x1b[0m  respuesta {i}\n\n")
        time.sleep(0.1)

    # Redraw header (it should always show the same lines).
    layout.header([
        "\x1b[36mBAGO v4.7.0\x1b[0m  \x1b[2m| provider: ollama-local | llama3.2:3b\x1b[0m",
        "\x1b[2m" + ("-" * 80) + "\x1b[0m",
    ])

    # Move cursor to bottom prompt.
    layout.prompt_line()
    # Print a fake user typing.
    sys.stdout.write("hola ")
    sys.stdout.flush()
    time.sleep(0.2)

    layout.exit()
    print("\x1b[32mok\x1b[0m layout test complete (only meaningful in a real terminal)")


if __name__ == "__main__":
    main()