from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bago_core.resolver import add_piece_paths, resolve_piece_path

INSTALLED_MARKERS = (
    "AppData\\Local\\BAGO",
    "Program Files\\BAGO",
    "C:\\Program Files\\BAGO",
    "C:\\Users\\AMTEC_Terminal_1º\\AppData\\Local\\BAGO",
)
MODULE_NAMES = {
    "renderer",
    "commands",
    "repl",
    "repl_banner",
    "repl_startup",
    "repl_menu",
    "repl_utils",
    "repl_inventory",
    "repl_wizard_project_v2",
    "repl_wizard_project_v6",
    "session_manager",
    "session_turn_mixin",
    "session_persistence_mixin",
    "session_context_workspace_mixin",
    "session_context_policy_mixin",
    "session_context_envelope_mixin",
    "switch_engine",
    "state_paths",
    "config_manager",
    "credential_manager",
    "script_registry",
    "tool_registry",
    "knowledge_base",
    "embedding_store",
    "agent_gateway",
    "plan_engine",
    "feedback_collector",
    "gabo_connector",
    "provider_adapter",
    "reflexive_interpreter",
    "contract_state",
    "guardrails",
    "path_guard",
    "tool_logger",
    "claim_validator",
    "context_commands",
    "memory_commands",
    "project_commands",
    "tool_approval_commands",
    "launcher",
}


def _ensure_local_paths() -> None:
    add_piece_paths("core.package", "chat.package", "providers.package", "api.package", "tools.package")
    # Ensure the legacy chat package wins over bago_core/commands when test
    # files import the bare `commands` module used by the .bago/chat REPL.
    chat_path = str(resolve_piece_path("chat.package"))
    if chat_path in sys.path:
        sys.path.remove(chat_path)
    sys.path.insert(0, chat_path)


def _bind_legacy_commands() -> None:
    """Force the bare `commands` name to the legacy .bago/chat dispatcher.

    Other test collection can load `bago_core.commands` first and leave the
    bare `commands` entry in ``sys.modules`` pointing at the modern package.
    Pre-binding prevents collection-order failures for REPL tests that do
    ``from commands import execute``.
    """
    import importlib

    sys.modules.pop("commands", None)
    importlib.import_module("commands")


def _is_bago_module(name: str, module: object) -> bool:
    if name in MODULE_NAMES or name.startswith("bago_core"):
        return True
    file = getattr(module, "__file__", None)
    if not file:
        return False
    file_text = str(Path(file))
    if any(marker in file_text for marker in INSTALLED_MARKERS):
        return True
    if str(REPO_ROOT) in file_text and "\\.bago\\" in file_text:
        return True
    return False


def _clear_bago_modules() -> None:
    _ensure_local_paths()
    for name, module in list(sys.modules.items()):
        if name == "commands":
            # Keep the legacy dispatcher bound once in pytest_configure so
            # collection-order races with bago_core.commands don't break.
            continue
        if _is_bago_module(name, module):
            sys.modules.pop(name, None)


def pytest_configure(config) -> None:  # noqa: D401
    _clear_bago_modules()
    _bind_legacy_commands()


def pytest_runtest_setup(item) -> None:  # noqa: D401
    _clear_bago_modules()
