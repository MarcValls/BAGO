#!/usr/bin/env python3
"""Menu y asistentes del REPL de BAGO, extraidos de repl.py."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import textwrap
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

# CANON[CHAT-002]: menu rendering is a projection of chat/session state, not authority.
# LEGACY[CHAT-L002]: add the chat directory to path so direct file imports still resolve peers.
CHAT_DIR = Path(__file__).resolve().parent
if str(CHAT_DIR) not in sys.path:
    sys.path.insert(0, str(CHAT_DIR))

import renderer as R
from commands import MENU_SECTIONS, menu_state_for_manager
from switch_engine import SwitchEngine
from repl_startup import CONFIG_EDITABLE
from tool_approval_commands import current_tool_approval_policy
from repl_utils import enable_vt, restore_windows_console, read_key, key_action, fit


def _load_tool_module(module_name: str, file_name: str):
    here = Path(__file__).resolve()
    path = here.with_name(file_name)
    if not path.exists():
        tools_dir = here.parents[1] / "tools" / file_name
        if tools_dir.exists():
            path = tools_dir
    spec = importlib.util.spec_from_file_location(f"bago.chat.{module_name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {file_name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _format_menu_audit_summary(data: dict[str, Any]) -> str:
    root = data.get("root") or data.get("project_root") or "—"
    stack = ", ".join(data.get("stack") or []) or "unknown"
    lines = [
        "Auditoría automática del directorio concreto:",
        f"  Project root: {root}",
        f"  Configured: {'yes' if data.get('configured') else 'no'}",
        f"  Linked: {'yes' if data.get('linked') else 'no'} ({data.get('link_mode', 'none')})",
        f"  Stack: {stack}",
    ]
    issues = list(data.get("issues") or [])[:3]
    if issues:
        lines.append("  Issues:")
        for item in issues:
            lines.append(f"    - {item}")
    suggestions = list(data.get("suggestions") or [])[:4]
    if suggestions:
        lines.append("  Suggested next checks: " + "; ".join(suggestions))
    return "\n".join(lines)


class BagoReplMenuMixin:

    _WIZARD_SHORT_NAMES = {
        "credentials": "credentials",
        "switch": "switch",
        "agent": "agent",
        "load": "load",
        "feedback": "feedback",
        "tools": "tools",
        "memory": "memory",
        "memory-delete": "memory-delete",
        "project": "project",
        "config": "config",
        "ui": "ui",
    }

    _WIZARD_COMMANDS = {
        "/credentials set": "credentials",
        "/switch": "switch",
        "/providers": "switch",
        "/models": "switch",
        "/bridges": "switch",
        "/agent": "agent",
        "/load": "load",
        "/config": "config",
        "/config set": "config",
        "/tools": "tools",
        "/feedback": "feedback",
        "/tools set": "tools",
        "/memory": "memory",
        "/memory delete": "memory-delete",
        "/project": "project",
        "/ui": "ui",
    }

    def _command_catalog(self) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        sections = []
        try:
            sections = menu_state_for_manager(self.mgr).get("sections", MENU_SECTIONS)
        except Exception:
            sections = MENU_SECTIONS
        for section in sections:
            for item in section["items"]:
                catalog.append({**item, "section": section["title"]})
        return catalog

    def _show_command_palette(self) -> bool:
        return self._show_menu()

    def _show_flat_command_palette(self) -> bool:
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            print(R.warn("Paleta no disponible en modo no interactivo. Usa /help."))
            return True
        catalog = self._command_catalog()
        labels = []
        for it in catalog:
            args = f" {it['args_prompt']}" if it.get("args_prompt") else ""
            labels.append(f"{it['command']}{args}  —  {it['description']}")
        idx = self._navigate("Comandos de BAGO  ·  vista completa", labels)
        if idx is None:
            print(R.dim("Paleta cerrada."))
            return True
        return self._run_menu_item(catalog[idx])

    def _show_menu(self) -> bool:
        if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
            print(R.warn("Menu no disponible en modo no interactivo. Usa /help."))
            return True
        try:
            menu_state = menu_state_for_manager(self.mgr)
            sections = menu_state.get("sections", MENU_SECTIONS)
        except Exception:
            menu_state = {}
            sections = MENU_SECTIONS
        while True:
            labels = [f"{section['title']}  —  {section['description']}" for section in sections]
            idx = self._navigate("Menu de funciones", labels)
            if idx is None:
                print(R.dim("Menu cerrado."))
                return True
            section = sections[idx]
            if len(section["items"]) == 1:
                result = self._run_menu_item(section["items"][0])
            else:
                result = self._show_menu_section(section)
            if result is None:
                continue
            return result

    def _show_menu_section(self, section: dict[str, Any]) -> bool | None:
        labels = []
        for item in section["items"]:
            args = f" {item['args_prompt']}" if item.get("args_prompt") else ""
            labels.append(f"{item['command']}{args}  —  {item['description']}")
        idx = self._navigate(section["title"], labels)
        if idx is None:
            return None
        return self._run_menu_item(section["items"][idx])

    def _run_menu_item(self, item: dict[str, Any]) -> bool:
        command_line = item["command"]
        wizard = item.get("wizard")
        if wizard:
            return self._run_wizard(wizard)
        if item.get("confirm"):
            try:
                confirm = input(R.warn(f"Confirma {command_line} (s/N): ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return True
            if confirm not in ("s", "si", "y", "yes"):
                print(R.dim("Operacion cancelada."))
                return True
        if item.get("args_prompt"):
            try:
                tail = input(R.dim(f"{command_line} {item['args_prompt']}: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return True
            if not tail:
                print(R.dim("Operacion cancelada."))
                return True
            command_line = f"{command_line} {tail}"
        return self._handle_command(command_line)

    def _run_wizard(self, name: str) -> bool:
        handlers = {
            "credentials": self._credential_wizard,
            "switch": self._switch_wizard,
            "agent": self._agent_wizard,
            "load": self._load_wizard,
            "feedback": self._feedback_wizard,
            "tools": self._tools_wizard,
            "memory": self._memory_hub_wizard,
            "memory-delete": self._memory_delete_wizard,
            "project": lambda: self._project_wizard(Path(self.mgr.base_path)),
            "config": self._config_wizard,
            "ui": self._ui_wizard,
            "inventory": self._inventory_wizard,
        }
        handler = handlers.get(name)
        if handler is None:
            print(R.error(f"Asistente desconocido: {name}"))
            return True
        return handler()

    def _wizard_tty_ok(self, manual_hint: str) -> bool:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return True
        print(R.warn(f"El asistente requiere un terminal interactivo. Usa: {manual_hint}"))
        return False

    def _provider_hub_wizard(self) -> bool:
        if not self._wizard_tty_ok("/providers | /models | /switch | /bridges"):
            return True
        try:
            providers = list(self.mgr.available_providers())
        except Exception as exc:
            print(R.error(f"No se pudieron listar los providers: {exc}"))
            return True
        if not providers:
            print(R.warn("No hay providers registrados."))
            return True

        provider_idx = 0
        for idx, item in enumerate(providers):
            if item.get("name") == self.mgr.provider:
                provider_idx = idx
                break
        model_idx = 0
        focus = "provider"
        notice = ""
        active_bridges = list(dict.fromkeys(self.mgr.active_bridges))
        if self.mgr.provider not in active_bridges:
            active_bridges.insert(0, self.mgr.provider)
        vt_ok = enable_vt()

        def _catalog(provider_name: str) -> list[dict[str, Any]]:
            try:
                return list(self.mgr.list_model_catalog(provider_name))
            except Exception:
                return []

        def _selected_provider() -> dict[str, Any]:
            nonlocal provider_idx
            provider_idx = max(0, min(provider_idx, len(providers) - 1))
            return providers[provider_idx]

        def _selected_catalog() -> list[dict[str, Any]]:
            provider = _selected_provider()
            return _catalog(provider["name"])

        def _sync_model_index() -> None:
            nonlocal model_idx
            catalog = _selected_catalog()
            if not catalog:
                model_idx = 0
                return
            provider = _selected_provider()
            ids = [item["id"] for item in catalog]
            if provider["name"] == self.mgr.provider and self.mgr.model in ids:
                model_idx = ids.index(self.mgr.model)
            else:
                model_idx = 0

        def _render() -> None:
            provider = _selected_provider()
            catalog = _selected_catalog()
            nonlocal model_idx
            if catalog:
                model_idx = max(0, min(model_idx, len(catalog) - 1))
            else:
                model_idx = 0

            cols = shutil.get_terminal_size((120, 32)).columns

            def _row(text: str, kind: str = "") -> str:
                plain = fit(text, cols)
                if kind == "selected":
                    return R.colorize(plain, R.Color.BG_CYAN, R.Color.BLACK, R.Color.BOLD)
                if kind == "current":
                    return R.colorize(plain, R.Color.BG_GREEN, R.Color.BLACK)
                if kind == "staged":
                    return R.colorize(plain, R.Color.BG_YELLOW, R.Color.BLACK)
                if kind == "warn":
                    return R.colorize(plain, R.Color.BG_RED, R.Color.WHITE)
                return plain

            lines = [
                "",
                R.bold("Providers / modelos / bridges"),
                R.dim(f"Actual: {self.mgr.provider}/{self.mgr.model}"),
                R.dim(f"Seleccionado: {provider['name']} · {catalog[model_idx]['id'] if catalog else 'sin-modelo'}"),
            ]
            if notice:
                lines.append(R.warn(notice))
            lines.append(R.dim(f"Bridges staged: {', '.join(active_bridges)}"))
            lines.append("")
            lines.append(R.bold("Providers"))
            for idx, item in enumerate(providers):
                marker = "❯" if focus == "provider" and idx == provider_idx else " "
                current = "●" if item.get("name") == self.mgr.provider else "○"
                bridge = "B" if item.get("name") in active_bridges else " "
                configured = "✓" if item.get("configured") else "✗"
                models = len(item.get("models") or [])
                line = f"{marker} {current}{bridge} {item['name']:<16} {configured} {models:>2} modelos"
                kind = "selected" if focus == "provider" and idx == provider_idx else ("current" if item.get("name") == self.mgr.provider else ("staged" if item.get("name") in active_bridges else ""))
                lines.append(_row(line, kind))
            lines.append("")
            lines.append(R.bold(f"Modelos de {provider['name']}"))
            if not catalog:
                lines.append(R.warn("  (sin modelos listados)"))
            else:
                for idx, item in enumerate(catalog[:12]):
                    marker = "❯" if focus == "model" and idx == model_idx else " "
                    current = "●" if provider["name"] == self.mgr.provider and item["id"] == self.mgr.model else "○"
                    staged = "✓" if idx == model_idx else " "
                    avail = "✓" if item.get("available", True) else "✗"
                    desc = item.get("best_for") or item.get("cost") or ""
                    line = f"{marker} {current}{staged}{avail} {item['id']:<24} {desc}"
                    kind = "selected" if focus == "model" and idx == model_idx else ("current" if provider["name"] == self.mgr.provider and item["id"] == self.mgr.model else ("staged" if idx == model_idx else ""))
                    lines.append(_row(line, kind))
                if len(catalog) > 12:
                    lines.append(R.dim(f"  ... y {len(catalog) - 12} más"))
            lines.extend([
                "",
                R.dim("Enter: cambia de foco · ↑↓ navega · ←→/Tab cambia panel"),
                R.dim("Espacio: marca/desmarca bridge · R: registrar provider · S: guardar · C/Esc: cancelar"),
            ])
            if vt_ok:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("\n".join(lines) + "\n")
                sys.stdout.flush()
            else:
                print("\n".join(lines))

        try:
            _sync_model_index()
            while True:
                _render()
                try:
                    key = read_key()
                except (EOFError, KeyboardInterrupt):
                    print()
                    print(R.dim("Centro cerrado."))
                    return True

                action = key_action(key, self.keybinds, "menu")
                provider = _selected_provider()
                catalog = _selected_catalog()

                if key == "LEFT":
                    focus = "provider" if focus == "model" else "model"
                    continue
                if action == "back" or key in {"c", "C"}:
                    print(R.dim("Centro cerrado."))
                    return True
                if action == "select":
                    focus = "model" if focus == "provider" else "provider"
                    continue
                if key in {"\t", "TAB"} or key == "RIGHT":
                    focus = "model" if focus == "provider" else "provider"
                    continue
                if action == "up":
                    if focus == "provider":
                        provider_idx = (provider_idx - 1) % len(providers)
                        _sync_model_index()
                    else:
                        if catalog:
                            model_idx = (model_idx - 1) % len(catalog)
                    continue
                if action == "down":
                    if focus == "provider":
                        provider_idx = (provider_idx + 1) % len(providers)
                        _sync_model_index()
                    else:
                        if catalog:
                            model_idx = (model_idx + 1) % len(catalog)
                    continue
                if key == " ":
                    name = provider["name"]
                    if name == self.mgr.provider:
                        notice = f"{name} es el provider actual; siempre queda activo."
                        continue
                    if name in active_bridges:
                        active_bridges = [item for item in active_bridges if item != name]
                        notice = f"Desmarcado bridge: {name}"
                    else:
                        active_bridges.append(name)
                        notice = f"Marcado bridge: {name}"
                    if self.mgr.provider not in active_bridges:
                        active_bridges.insert(0, self.mgr.provider)
                    continue
                if key in {"r", "R"}:
                    if not provider.get("configured", False):
                        notice = f"Registrando {provider['name']}..."
                    ok = self._credential_wizard_provider(provider["name"])
                    providers = list(self.mgr.available_providers())
                    if providers:
                        provider_names = [item["name"] for item in providers]
                        if provider["name"] in provider_names:
                            provider_idx = provider_names.index(provider["name"])
                        elif self.mgr.provider in provider_names:
                            provider_idx = provider_names.index(self.mgr.provider)
                    _sync_model_index()
                    notice = f"✓ {provider['name']} actualizado" if ok else f"Registro cancelado para {provider['name']}"
                    continue
                if key in {"s", "S"}:
                    catalog = _selected_catalog()
                    target_provider = provider["name"]
                    target_model = catalog[model_idx]["id"] if catalog else None
                    if target_provider != self.mgr.provider or (target_model and target_model != self.mgr.model):
                        result = self.mgr.switch(target_provider, target_model, force=True)
                        if not result.get("ok"):
                            notice = result.get("error") or result.get("warnings", ["?"])[0]
                            continue
                        warnings = list(result.get("warnings") or [])
                        if warnings:
                            notice = " | ".join(warnings[:2])
                        else:
                            notice = f"✓ {target_provider}/{self.mgr.model}"
                        self.engine = SwitchEngine(self.mgr.adapters)
                    self.mgr.set_active_bridges(active_bridges)
                    try:
                        self.mgr.save()
                    except Exception:
                        pass
                    print(R.ok(f"✓ Guardado: {self.mgr.provider}/{self.mgr.model}"))
                    print(R.dim(f"  bridges activos: {', '.join(self.mgr.active_bridges)}"))
                    return True
        finally:
            restore_windows_console()

    def _config_hub_wizard(self) -> bool:
        if not self._wizard_tty_ok("/config"):
            return True
        try:
            items = list(CONFIG_EDITABLE)
        except Exception as exc:
            print(R.error(f"No se pudo cargar la configuracion editable: {exc}"))
            return True
        if not items:
            print(R.warn("No hay ajustes editables."))
            return True

        original: dict[str, Any] = {key: self.mgr.config.get(key, "") for key, _typ, _desc in items}
        staged: dict[str, Any] = dict(original)
        selected = 0
        notice = ""
        vt_ok = enable_vt()
        choice_map: dict[str, tuple[str, ...]] = {
            "features.tool_approval_policy": ("ask", "always"),
        }

        def _selected_item() -> tuple[str, str, str]:
            nonlocal selected
            selected = max(0, min(selected, len(items) - 1))
            return items[selected]

        def _changed_count() -> int:
            return sum(1 for key, _typ, _desc in items if staged.get(key) != original.get(key))

        def _display_value(key: str, typ: str) -> str:
            value = staged.get(key, "")
            if typ == "bool":
                return "true" if bool(value) else "false"
            if typ == "number":
                try:
                    return f"{float(value):g}"
                except Exception:
                    return str(value)
            return str(value)

        def _preview_runtime(key: str) -> None:
            if key == "ui.color":
                R.set_color_enabled(bool(staged.get(key, True)))

        def _render() -> None:
            cols = shutil.get_terminal_size((120, 36)).columns

            def _row(text: str, kind: str = "") -> str:
                plain = fit(text, cols)
                if kind == "selected":
                    return R.colorize(plain, R.Color.BG_CYAN, R.Color.BLACK, R.Color.BOLD)
                if kind == "dirty":
                    return R.colorize(plain, R.Color.BG_YELLOW, R.Color.BLACK)
                return plain

            lines = [
                "",
                R.bold("Configuracion / defaults"),
                R.dim(f"Pendientes sin guardar: {_changed_count()}"),
                R.dim("Enter/espacio: alterna o edita · R: restaurar · S: guardar · C/Esc: cancelar"),
                R.dim("La sesion activa se cambia en /providers; aqui guardas defaults y flags."),
            ]
            if notice:
                lines.append(R.warn(notice))
            lines.append("")
            for idx, (key, typ, desc) in enumerate(items):
                marker = "❯" if idx == selected else " "
                dirty = "*" if staged.get(key) != original.get(key) else " "
                value = _display_value(key, typ)
                line = f"{marker} {dirty} {key:<34} {value:<18} {desc}"
                lines.append(_row(line, "selected" if idx == selected else ("dirty" if staged.get(key) != original.get(key) else "")))
            if vt_ok:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("\n".join(lines) + "\n")
                sys.stdout.flush()
            else:
                print("\n".join(lines))

        try:
            _preview_runtime("ui.color")
            while True:
                _render()
                try:
                    key = read_key()
                except (EOFError, KeyboardInterrupt):
                    print()
                    R.set_color_enabled(bool(original.get("ui.color", True)))
                    print(R.dim("Configuracion cerrada."))
                    return True

                if key == "LEFT":
                    selected = (selected - 1) % len(items)
                    continue
                if key in {"\t", "TAB", "RIGHT"}:
                    selected = (selected + 1) % len(items)
                    continue

                action = key_action(key, self.keybinds, "menu")
                key_name, typ, desc = _selected_item()
                current = staged.get(key_name, "")

                if action == "back" or key in {"c", "C"}:
                    R.set_color_enabled(bool(original.get("ui.color", True)))
                    print(R.dim("Configuracion cerrada."))
                    return True
                if action == "up":
                    selected = (selected - 1) % len(items)
                    continue
                if action == "down":
                    selected = (selected + 1) % len(items)
                    continue
                if key in {"r", "R"}:
                    staged[key_name] = original.get(key_name, "")
                    _preview_runtime(key_name)
                    notice = f"Restaurado: {key_name}"
                    continue
                if action == "select" or key == " ":
                    if typ == "bool":
                        staged[key_name] = not bool(current)
                        _preview_runtime(key_name)
                        notice = f"{key_name} -> {_display_value(key_name, typ)}"
                        continue
                    if typ == "choice":
                        choices = choice_map.get(key_name, ())
                        if not choices:
                            notice = f"{key_name} no admite ciclo."
                            continue
                        current_text = str(current)
                        try:
                            pos = choices.index(current_text)
                        except ValueError:
                            pos = -1
                        staged[key_name] = choices[(pos + 1) % len(choices)]
                        notice = f"{key_name} -> {staged[key_name]}"
                        continue
                    print(R.dim(f"  {desc}"))
                    value = self._timed_input(R.accent(f"  {key_name} = "), timeout=60)
                    if value is None:
                        notice = "Edición cancelada."
                        continue
                    value = value.strip()
                    if not value:
                        notice = "Valor vacío. Cambio cancelado."
                        continue
                    try:
                        if typ == "number":
                            parsed: Any = float(value)
                        else:
                            parsed = value
                    except ValueError:
                        notice = "Valor inválido."
                        continue
                    staged[key_name] = parsed
                    _preview_runtime(key_name)
                    notice = f"{key_name} preparado: {_display_value(key_name, typ)}"
                    continue
                if key in {"s", "S"}:
                    changed_keys = [k for k, _t, _d in items if staged.get(k) != original.get(k)]
                    if not changed_keys:
                        R.set_color_enabled(bool(staged.get("ui.color", original.get("ui.color", True))))
                        print(R.dim("No había cambios que guardar."))
                        return True
                    errors: list[str] = []
                    for cfg_key in changed_keys:
                        try:
                            if cfg_key == "features.tool_approval_policy":
                                normalized = str(staged[cfg_key])
                                if hasattr(self.mgr, "set_tool_approval_policy"):
                                    normalized = self.mgr.set_tool_approval_policy(normalized)
                                else:
                                    normalized = "always" if normalized == "always" else "ask"
                                    self.mgr.config.set("features.tool_approval_policy", normalized)
                                    self.mgr.config.set("features.auto_allow_tools", normalized == "always")
                                staged[cfg_key] = normalized
                            else:
                                self.mgr.config.set(cfg_key, staged[cfg_key])
                        except Exception as exc:
                            errors.append(f"{cfg_key}: {exc}")
                    R.set_color_enabled(bool(staged.get("ui.color", original.get("ui.color", True))))
                    if errors:
                        print(R.error("No se pudo guardar la configuración:"))
                        for err in errors[:3]:
                            print(R.error(f"  {err}"))
                        return True
                    print(R.ok(f"✓ Guardado: {len(changed_keys)} cambio(s)"))
                    if "features.tool_approval_policy" in changed_keys:
                        print(R.dim(f"  tool_approval_policy: {self.mgr.tool_approval_policy()}"))
                    return True
        finally:
            restore_windows_console()

    def _switch_wizard(self) -> bool:
        return self._provider_hub_wizard()

    def _agent_wizard(self) -> bool:
        if not self._wizard_tty_ok("/agent <nombre>"):
            return True
        try:
            agents = self.mgr.agent_gateway.list_agents()
        except Exception as exc:
            print(R.error(f"No se pudieron listar los agentes: {exc}"))
            return True
        if not agents:
            print(R.warn("No hay agentes disponibles."))
            return True

        active = self.mgr.agent_gateway.active.name
        labels = []
        for agent in agents:
            marker = "✓" if agent.name == active else "○"
            labels.append(f"{marker} {agent.name}  ·  {agent.description}")
        idx = self._navigate("Agentes especializados · elige uno", labels)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        name = agents[idx].name
        return self._handle_command(f"/agent {name}")

    def _load_wizard(self) -> bool:
        if not self._wizard_tty_ok("/load <session_id>"):
            return True
        sessions_dir = self.state_root / "sessions"
        if not sessions_dir.exists():
            print(R.warn("No hay sesiones guardadas."))
            return True

        items: list[tuple[str, str, str]] = []
        for path in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            sid = str(data.get("session_id") or path.stem)
            created = str(data.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)))
            provider = str(data.get("provider") or "?")
            model = str(data.get("model") or "?")
            items.append((sid, created, f"{provider}/{model}"))

        if not items:
            print(R.warn("No hay sesiones guardadas."))
            return True

        labels = [f"{sid}  ·  {created}  ·  {prov_model}" for sid, created, prov_model in items]
        idx = self._navigate("Cargar sesión · elige una", labels)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        sid = items[idx][0]
        return self._handle_command(f"/load {sid}")

    def _project_wizard(self, project_root: Path) -> bool:
        if not self._wizard_tty_ok("/project [analyze|status|init|link]"):
            return True
        mod = _load_tool_module("project_memory", "project_memory.py")
        detected_root = Path(project_root).expanduser().resolve()

        def _bind(root: Path) -> None:
            try:
                self.mgr.rebind_project_root(root)
                print(R.ok(f"Proyecto activo: {root}"))
            except Exception as exc:
                print(R.warn(f"No se pudo activar el proyecto: {exc}"))

        labels = [
            f"Usar esta ruta como proyecto activo y analizar ({detected_root.name})" if detected_root != project_root else f"Usar este directorio como proyecto activo y analizar ({project_root.name})",
            "Ver estado del proyecto",
            "Inicializar estructura .bago",
            "Vincular proyecto portable",
            "Elegir otra ruta de proyecto",
            "Seguir con la sesión",
        ]
        idx = self._navigate(f"Proyecto detectado · {detected_root}", labels)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        if idx == 0:
            _bind(detected_root)
            data = mod.analyze_data(detected_root)
            if hasattr(self.mgr, "record_project_analysis"):
                self.mgr.record_project_analysis(data)
            print(mod.format_analysis(data))
            return True
        if idx == 1:
            _bind(detected_root)
            data = mod.status_data(detected_root)
            print(mod.format_status(data))
            return True
        if idx == 2:
            _bind(detected_root)
            data = mod.init_project(detected_root)
            print(R.ok(f"Proyecto inicializado: {data['bago_dir']}"))
            return True
        if idx == 3:
            _bind(detected_root)
            data = mod.link_project(detected_root)
            print(R.ok(f"Proyecto vinculado: {data['root']} ({data['link_mode']})"))
            return True
        if idx == 4:
            try:
                raw = input(R.dim("Ruta del proyecto: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return True
            if not raw:
                print(R.dim("Ruta vacía."))
                return True
            chosen = Path(raw).expanduser().resolve()
            if not chosen.exists() or not chosen.is_dir():
                print(R.warn(f"Ruta inválida: {chosen}"))
                return True
            _bind(chosen)
            data = mod.analyze_data(chosen)
            if hasattr(self.mgr, "record_project_analysis"):
                self.mgr.record_project_analysis(data)
            print(mod.format_analysis(data))
            return True
        return True

    def _feedback_wizard(self) -> bool:
        if not self._wizard_tty_ok("/feedback <rating>"):
            return True
        opts = ["Positivo (+1)", "Neutro (0)", "Negativo (-1)"]
        vals = ["1", "0", "-1"]
        idx = self._navigate("Feedback de la ultima respuesta", opts)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        return self._handle_command(f"/feedback {vals[idx]}")

    def _tools_wizard(self) -> bool:
        if not self._wizard_tty_ok("/tools"):
            return True
        try:
            tools = list(self.mgr.tool_registry)
        except Exception as exc:
            print(R.error(f"No se pudieron listar las herramientas: {exc}"))
            return True

        staged_calling = bool(self.mgr.config.get("features.tool_calling", False))
        staged_policy = current_tool_approval_policy(self.mgr)
        original_calling = staged_calling
        original_policy = staged_policy
        selected = 0
        notice = ""
        vt_ok = enable_vt()

        def _pending_tools() -> list[dict[str, Any]]:
            return list(getattr(self.mgr, "_pending_tools", None) or [])

        def _snippet(text: str, width: int = 88) -> str:
            flat = " ".join(str(text).split())
            if len(flat) <= width:
                return flat
            return flat[: max(1, width - 1)] + "…"

        def _render() -> None:
            current = bool(self.mgr.config.get("features.tool_calling", False))
            policy = current_tool_approval_policy(self.mgr)
            pending = _pending_tools()
            cols = shutil.get_terminal_size((120, 36)).columns
            lines = [
                "",
                R.bold("Herramientas / automatizacion"),
                R.dim(f"Actual: tools={'on' if current else 'off'} · aprobacion={policy} · pendientes={len(pending)}"),
                R.dim(f"Staged: tools={'on' if staged_calling else 'off'} · aprobacion={staged_policy}"),
                R.dim("Espacio: alterna tools · P: ask/always · a: aprobar una vez · A: aprobar siempre · d: rechazar una vez"),
                R.dim("R: refrescar · S: guardar · C/Esc: cancelar"),
            ]
            if notice:
                lines.append(R.warn(notice))
            lines.append("")
            lines.append(R.bold("Registro de tools"))
            if not tools:
                lines.append(R.warn("  (sin herramientas registradas)"))
            else:
                for idx, item in enumerate(tools):
                    name = str(item[0])
                    tool = item[1]
                    desc = _snippet(str(getattr(tool, "description", "") or ""), width=cols - 32)
                    line = fit(f"  {name:<28} {desc}", cols)
                    if idx == selected:
                        line = R.colorize(line, R.Color.BG_CYAN, R.Color.BLACK, R.Color.BOLD)
                    lines.append(line)
            lines.append("")
            if pending:
                lines.append(R.bold("Pendientes"))
                for tc in pending[:5]:
                    func = tc.get("function", {})
                    name = func.get("name", "unknown")
                    args = _snippet(str(func.get("arguments", "{}")), width=max(24, cols - 18))
                    lines.append(R.colorize(fit(f"  • {name}: {args}", cols), R.Color.BG_YELLOW, R.Color.BLACK))
                if len(pending) > 5:
                    lines.append(R.dim(f"  ... y {len(pending) - 5} más"))
            else:
                lines.append(R.dim("Sin solicitudes pendientes de aprobación."))
            if vt_ok:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("\n".join(lines) + "\n")
                sys.stdout.flush()
            else:
                print("\n".join(lines))

        try:
            while True:
                _render()
                try:
                    key = read_key()
                except (EOFError, KeyboardInterrupt):
                    print()
                    print(R.dim("Herramientas cerradas."))
                    return True

                action = key_action(key, self.keybinds, "menu")

                if action == "back" or key in {"c", "C"}:
                    print(R.dim("Herramientas cerradas."))
                    return True
                if action == "up":
                    if tools:
                        selected = (selected - 1) % len(tools)
                    continue
                if action == "down":
                    if tools:
                        selected = (selected + 1) % len(tools)
                    continue
                if key in {"\t", "TAB", "LEFT", "RIGHT"}:
                    continue
                if key in {"r", "R"}:
                    try:
                        tools = list(self.mgr.tool_registry)
                    except Exception as exc:
                        notice = f"No se pudo refrescar el catálogo: {exc}"
                        continue
                    selected = min(selected, len(tools) - 1) if tools else 0
                    notice = "Catálogo refrescado."
                    continue
                if action == "select" or key == " ":
                    staged_calling = not staged_calling
                    notice = f"tool_calling -> {'on' if staged_calling else 'off'}"
                    continue
                if key in {"p", "P"}:
                    staged_policy = "always" if staged_policy == "ask" else "ask"
                    notice = f"aprobacion -> {staged_policy}"
                    continue
                if key in {"a", "A", "d", "D"}:
                    if key in {"a", "A"}:
                        mode = "always" if key == "A" else "once"
                        result = self.mgr.approve_tools(mode)
                    else:
                        result = self.mgr.deny_tools("once")
                    if result:
                        print(R.ok(result))
                    continue
                if key in {"s", "S"}:
                    changed: list[str] = []
                    try:
                        if staged_calling != original_calling:
                            self.mgr.config.set("features.tool_calling", staged_calling)
                            changed.append("features.tool_calling")
                        if staged_policy != original_policy:
                            if hasattr(self.mgr, "set_tool_approval_policy"):
                                staged_policy = self.mgr.set_tool_approval_policy(staged_policy)
                            else:
                                self.mgr.config.set("features.tool_approval_policy", staged_policy)
                                self.mgr.config.set("features.auto_allow_tools", staged_policy == "always")
                            changed.append("features.tool_approval_policy")
                    except Exception as exc:
                        print(R.error(f"No se pudo guardar la configuración de tools: {exc}"))
                        return True
                    if not changed:
                        print(R.dim("No había cambios que guardar."))
                        return True
                    print(R.ok(f"✓ Guardado: tools={'on' if staged_calling else 'off'} · aprobación={staged_policy}"))
                    return True
        finally:
            restore_windows_console()

    def _pending_tool_approval_wizard(self) -> bool:
        pending = list(getattr(self.mgr, "_pending_tools", None) or [])
        if not pending:
            return False
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            return False

        policy = getattr(self.mgr, "tool_approval_policy", lambda: self.mgr.config.get("features.tool_approval_policy", "ask"))()
        print(R.dim("Solicitud de herramientas pendiente:"))
        for tc in pending[:6]:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            args = func.get("arguments", "{}")
            print(R.dim(f"  • {name}: {args}"))
        if len(pending) > 6:
            print(R.dim(f"  … y {len(pending) - 6} más"))

        idx = self._navigate(
            f"Aprobación de herramientas · política actual: {policy}",
            [
                "Ejecutar una vez",
                "Permitir siempre",
                "Preguntar siempre",
                "Rechazar",
            ],
        )
        if idx is None:
            return False

        if idx == 0:
            result = self.mgr.approve_tools("once")
            if result:
                R.print_message("assistant", result)
            return True
        if idx == 1:
            result = self.mgr.approve_tools("always")
            if result:
                R.print_message("assistant", result)
            return True
        if idx == 2:
            result = self.mgr.deny_tools("ask")
            if result:
                print(R.ok(result))
            return True
        result = self.mgr.deny_tools("once")
        if result:
            print(R.ok(result))
        return True

    def _memory_delete_wizard(self) -> bool:
        return self._memory_hub_wizard()

    def _memory_hub_wizard(self) -> bool:
        if not self._wizard_tty_ok("/memory"):
            return True
        try:
            recent = list(self.mgr.knowledge.list_recent(limit=20))
        except Exception as exc:
            print(R.error(f"No se pudieron listar los recuerdos: {exc}"))
            return True
        if not recent:
            print(R.warn("No hay recuerdos almacenados."))
            return True

        selected = 0
        staged_delete: set[int] = set()
        notice = ""
        vt_ok = enable_vt()

        def _selected_item() -> dict[str, Any]:
            nonlocal selected
            selected = max(0, min(selected, len(recent) - 1))
            return recent[selected]

        def _snippet(text: str, width: int = 90) -> str:
            flat = " ".join(str(text).split())
            if len(flat) <= width:
                return flat
            return flat[: max(1, width - 1)] + "…"

        def _preview_lines(text: str, cols: int) -> list[str]:
            lines: list[str] = []
            for raw in str(text).splitlines() or [""]:
                wrapped = textwrap.wrap(
                    raw,
                    width=max(20, cols - 6),
                    replace_whitespace=False,
                    drop_whitespace=False,
                )
                if wrapped:
                    lines.extend(wrapped)
                else:
                    lines.append("")
            return lines

        def _render() -> None:
            item = _selected_item()
            cols = shutil.get_terminal_size((120, 38)).columns

            def _row(text: str, kind: str = "") -> str:
                plain = fit(text, cols)
                if kind == "selected":
                    return R.colorize(plain, R.Color.BG_CYAN, R.Color.BLACK, R.Color.BOLD)
                if kind == "delete":
                    return R.colorize(plain, R.Color.BG_RED, R.Color.WHITE)
                return plain

            lines = [
                "",
                R.bold("Memoria / recuerdos"),
                R.dim(f"Recientes: {len(recent)} · marcados para borrar: {len(staged_delete)}"),
                R.dim("↑↓ navega · espacio marca/desmarca · S borra marcados · C/Esc cancela"),
            ]
            if notice:
                lines.append(R.warn(notice))
            lines.append("")
            lines.append(R.bold("Lista"))
            for idx, row in enumerate(recent):
                marker = "❯" if idx == selected else " "
                staged = "✗" if int(row["id"]) in staged_delete else " "
                when = str(row.get("created_at", ""))[:19]
                source = str(row.get("source_session", "") or "—")[:12]
                snippet = _snippet(str(row.get("content", "")), width=72)
                line = f"{marker} {staged} {int(row['id']):>4} | {when} | {source:<12} | {snippet}"
                kind = "delete" if int(row["id"]) in staged_delete else ("selected" if idx == selected else "")
                lines.append(_row(line, kind))
            lines.append("")
            lines.append(R.bold("Vista previa"))
            lines.append(_row(f"  ID: {item['id']} · session: {item.get('source_session') or '—'}", "delete" if int(item["id"]) in staged_delete else "selected"))
            lines.append(_row(f"  created_at: {item.get('created_at')}", "delete" if int(item["id"]) in staged_delete else ""))
            lines.append("  content:")
            preview = _preview_lines(str(item.get("content", "")), cols)
            if preview:
                lines.extend([f"    {line}" for line in preview])
            else:
                lines.append("    (vacío)")
            if vt_ok:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("\n".join(lines) + "\n")
                sys.stdout.flush()
            else:
                print("\n".join(lines))

        try:
            while True:
                _render()
                try:
                    key = read_key()
                except (EOFError, KeyboardInterrupt):
                    print()
                    print(R.dim("Memoria cerrada."))
                    return True

                action = key_action(key, self.keybinds, "menu")
                item = _selected_item()
                mid = int(item["id"])

                if action == "back" or key in {"c", "C"}:
                    print(R.dim("Memoria cerrada."))
                    return True
                if action == "up":
                    selected = (selected - 1) % len(recent)
                    continue
                if action == "down":
                    selected = (selected + 1) % len(recent)
                    continue
                if key in {"\t", "TAB", "LEFT", "RIGHT"}:
                    continue
                if action == "select" or key in {" ", "d", "D"}:
                    if mid in staged_delete:
                        staged_delete.remove(mid)
                        notice = f"Desmarcado {mid}."
                    else:
                        staged_delete.add(mid)
                        notice = f"Marcado {mid} para borrar."
                    continue
                if key in {"r", "R"}:
                    try:
                        refreshed = list(self.mgr.knowledge.list_recent(limit=20))
                    except Exception as exc:
                        notice = f"No se pudo refrescar: {exc}"
                        continue
                    if refreshed:
                        recent = refreshed
                        if mid in [int(row["id"]) for row in recent]:
                            selected = next(i for i, row in enumerate(recent) if int(row["id"]) == mid)
                        else:
                            selected = min(selected, len(recent) - 1)
                        notice = "Lista refrescada."
                    continue
                if key in {"s", "S"}:
                    if not staged_delete:
                        print(R.dim("No hay recuerdos marcados para borrar."))
                        return True
                    deleted: list[int] = []
                    failed: list[int] = []
                    for memory_id in sorted(staged_delete):
                        try:
                            if self.mgr.knowledge.delete(memory_id):
                                deleted.append(memory_id)
                            else:
                                failed.append(memory_id)
                        except Exception:
                            failed.append(memory_id)
                    print(R.ok(f"✓ Eliminados: {len(deleted)}"))
                    if deleted:
                        print(R.dim("  IDs: " + ", ".join(str(mid) for mid in deleted[:8])))
                    if failed:
                        print(R.warn("No se pudieron borrar algunos IDs: " + ", ".join(str(mid) for mid in failed[:8])))
                    return True
        finally:
            restore_windows_console()

    def _credential_wizard(self) -> bool:
        if not self._wizard_tty_ok("/credentials set <provider> <key> <valor>"):
            return True
        try:
            from credential_manager import CREDENTIAL_SCHEMA
        except Exception as exc:
            print(R.error(f"No se pudo cargar el esquema: {exc}"))
            return True

        creds = self.mgr.credentials
        providers = list(CREDENTIAL_SCHEMA.keys())
        plabels = []
        for p in providers:
            mark = "✓" if creds.is_configured(p) else "○"
            plabels.append(f"{mark} {p}")
        pidx = self._navigate("Registrar credencial · elige provider", plabels)
        if pidx is None:
            return True
        return self._credential_wizard_provider(providers[pidx])

    def _credential_wizard_provider(self, provider: str, silent: bool = False) -> bool:
        LOGIN_URLS = {
            "copilot": "https://github.com/settings/tokens",
            "codex": "https://platform.openai.com/api-keys",
            "anthropic": "https://console.anthropic.com/settings/keys",
            "openrouter": "https://openrouter.ai/keys",
            "opencode": "https://opencode.ai",
            "ollama-cloud": "https://ollama.com/signin",
        }

        print(R.info(f"🔑 Configurando {provider}"))
        detected = False

        if provider == "copilot":
            try:
                r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10, shell=(sys.platform == "win32"))
                if r.returncode == 0 and r.stdout.strip():
                    self.mgr.credentials.set("copilot", "GITHUB_TOKEN", r.stdout.strip())
                    detected = True
                    print(R.ok("  ✓ Token detectado via gh CLI"))
            except Exception:
                pass
            if not detected and os.environ.get("GITHUB_TOKEN"):
                self.mgr.credentials.set("copilot", "GITHUB_TOKEN", os.environ["GITHUB_TOKEN"])
                detected = True
                print(R.ok("  ✓ Token detectado en entorno"))

        elif provider == "codex":
            for p in [Path.home() / ".codex" / "auth.json", Path.home() / "AppData" / "Roaming" / "OpenAI" / "auth.json"]:
                if p.exists():
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        token = data.get("api_key") or data.get("session_token") or data.get("access_token")
                        if token:
                            self.mgr.credentials.set("codex", "OPENAI_API_KEY", token)
                            detected = True
                            print(R.ok("  ✓ Token de Codex Desktop detectado"))
                            break
                    except Exception:
                        pass
            if not detected and os.environ.get("OPENAI_API_KEY"):
                self.mgr.credentials.set("codex", "OPENAI_API_KEY", os.environ["OPENAI_API_KEY"])
                detected = True
                print(R.ok("  ✓ API key detectada en entorno"))

        elif provider == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            self.mgr.credentials.set("anthropic", "ANTHROPIC_API_KEY", os.environ["ANTHROPIC_API_KEY"])
            detected = True
            print(R.ok("  ✓ Key detectada en entorno"))

        elif provider == "openrouter" and os.environ.get("OPENROUTER_API_KEY"):
            self.mgr.credentials.set("openrouter", "OPENROUTER_API_KEY", os.environ["OPENROUTER_API_KEY"])
            detected = True
            print(R.ok("  ✓ Key detectada en entorno"))

        elif provider == "opencode" and os.environ.get("OPENCODE_API_KEY"):
            self.mgr.credentials.set("opencode", "OPENCODE_API_KEY", os.environ["OPENCODE_API_KEY"])
            detected = True
            print(R.ok("  ✓ Key detectada en entorno"))

        elif provider == "ollama-local":
            for host in ["http://127.0.0.1:11434", "http://localhost:11434"]:
                try:
                    req = urllib.request.Request(f"{host}/api/tags", method="GET")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        if resp.status == 200:
                            self.mgr.credentials.set("ollama-local", "OLLAMA_HOST", host)
                            detected = True
                            print(R.ok(f"  ✓ Ollama detectado en {host}"))
                            break
                except Exception:
                    pass
            if not detected:
                self.mgr.credentials.set("ollama-local", "OLLAMA_HOST", "http://127.0.0.1:11434")
                detected = True
                print(R.info("  ℹ Ollama no detectado, configurado para localhost:11434"))

        elif provider == "ollama-cloud":
            self.mgr.credentials.set("ollama-cloud", "OLLAMA_CLOUD_URL", "https://ollama.com")

        if not detected and provider in LOGIN_URLS:
            url = LOGIN_URLS[provider]
            print(R.info(f"  Abriendo {url} ..."))
            try:
                webbrowser.open(url)
            except Exception:
                pass

        from credential_manager import CREDENTIAL_SCHEMA
        schema = CREDENTIAL_SCHEMA.get(provider, {})
        stored = self.mgr.credentials.list_for_provider(provider)

        for key, desc in schema.items():
            if stored.get(key):
                continue
            is_optional = "opcional" in desc.lower()
            prompt = f"  {key}: "
            if is_optional:
                prompt = f"  {key} (opcional, Enter para omitir): "
            val = self._timed_input(R.accent(prompt), timeout=120)
            if val is None:
                print(R.dim("  Cancelado."))
                return False
            val = val.strip()
            if not val and is_optional:
                continue
            if not val and not is_optional:
                print(R.error("  Campo obligatorio. Cancelado."))
                return False
            self.mgr.credentials.set(provider, key, val)
            print(R.ok(f"  ✓ {key} guardado"))

        if not silent:
            print()
            print(R.ok(f"✓ {provider} configurado."))
        if provider != "ollama-local":
            result = self.mgr.switch(provider, force=True)
            if result.get("ok"):
                if not silent:
                    print(R.ok(f"✓ Conectado a {provider}/{self.mgr.model}"))
                self.engine = SwitchEngine(self.mgr.adapters)
            else:
                err = result.get("error") or result.get("warnings", ["?"])[0]
                if not silent:
                    print(R.error(f"✗ No se pudo conectar: {err}"))
                return False
        return True

    def _ui_config_path(self) -> Path:
        here = Path(__file__).resolve()
        return here.parents[2] / "ui-react" / "public" / "ui_config.json"

    def _ui_load_config(self) -> dict:
        path = self._ui_config_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _ui_save_config(self, cfg: dict) -> None:
        path = self._ui_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def _ui_wizard(self) -> bool:
        if not self._wizard_tty_ok("/ui [tema|layout|version|branding]"):
            return True
        cfg = self._ui_load_config()
        labels = [
            "Tema visual (colores, modo dark/light)",
            "Layout (paneles visibles)",
            "Version y branding",
            "Ver config actual",
            "Salir",
        ]
        idx = self._navigate("Configuracion UI · elige uno", labels)
        if idx is None or idx == 4:
            print(R.dim("Asistente cerrado."))
            return True
        if idx == 0:
            return self._ui_theme_wizard(cfg)
        if idx == 1:
            return self._ui_layout_wizard(cfg)
        if idx == 2:
            return self._ui_version_wizard(cfg)
        if idx == 3:
            print(R.dim(json.dumps(cfg, indent=2, ensure_ascii=False)))
            return True
        return True

    def _ui_theme_wizard(self, cfg: dict) -> bool:
        theme = cfg.get("theme", {})
        presets = {
            "dark (actual)": {"mode": "dark", "bg": "#050813", "bg2": "#08101f", "panel": "#0f172a", "panel2": "#121d32", "panel3": "#17233d", "text": "#e8eefb", "muted": "#91a5c0", "brand": "#7c8cff", "brandStrong": "#4658ff", "cyan": "#22d3ee", "ok": "#34d399", "warn": "#fbbf24", "danger": "#fb7185", "violet": "#c084fc", "orange": "#fb923c", "radius": "20px"},
            "light": {"mode": "light", "bg": "#f8fafc", "bg2": "#f1f5f9", "panel": "#ffffff", "panel2": "#f8fafc", "panel3": "#e2e8f0", "text": "#1e293b", "muted": "#64748b", "brand": "#4658ff", "brandStrong": "#4658ff", "cyan": "#0891b2", "ok": "#059669", "warn": "#d97706", "danger": "#e11d48", "violet": "#9333ea", "orange": "#ea580c", "radius": "20px"},
            "midnight": {"mode": "dark", "bg": "#0a0a0a", "bg2": "#141414", "panel": "#1a1a1a", "panel2": "#222222", "panel3": "#2a2a2a", "text": "#e0e0e0", "muted": "#888888", "brand": "#6366f1", "brandStrong": "#4f46e5", "cyan": "#06b6d4", "ok": "#10b981", "warn": "#f59e0b", "danger": "#ef4444", "violet": "#a855f7", "orange": "#f97316", "radius": "12px"},
        }
        labels = list(presets.keys())
        idx = self._navigate("Tema visual · elige un preset", labels)
        if idx is None:
            print(R.dim("Cancelado."))
            return True
        chosen = list(presets.values())[idx]
        cfg.setdefault("theme", {}).update(chosen)
        self._ui_save_config(cfg)
        print(R.ok(f"✓ Tema '{labels[idx]}' guardado. Recarga la UI (Ctrl+R en el navegador)."))
        return True

    def _ui_layout_wizard(self, cfg: dict) -> bool:
        layout = cfg.get("layout", {})
        keys = ["showKit", "showDock", "showInspector", "showContextPane", "showManagerDrawer", "sidebarCollapsed", "chatFocus"]
        labels_ko = {"showKit": "Session Kit", "showDock": "Pipeline Dock", "showInspector": "Inspector", "showContextPane": "Context Pane", "showManagerDrawer": "Manager Drawer", "sidebarCollapsed": "Sidebar colapsado", "chatFocus": "Chat centrado"}
        current_labels = []
        for k in keys:
            val = layout.get(k, False)
            current_labels.append(f"{'✓' if val else '○'} {labels_ko.get(k, k)}")
        idx = self._navigate("Layout · toggle un panel", current_labels)
        if idx is None:
            print(R.dim("Cancelado."))
            return True
        key = keys[idx]
        cfg.setdefault("layout", {})[key] = not layout.get(key, False)
        self._ui_save_config(cfg)
        new_val = cfg["layout"][key]
        print(R.ok(f"✓ {labels_ko.get(key, key)} = {'visible' if new_val else 'oculto'}. Recarga la UI."))
        return True

    def _ui_version_wizard(self, cfg: dict) -> bool:
        current = cfg.get("version", "?")
        brand = cfg.get("brand", {})
        labels = [
            f"Version actual: {current}",
            "Cambiar version",
            f"Cambiar nombre de marca (actual: {brand.get('name', 'BAGO')})",
            f"Cambiar simbolo (actual: {brand.get('symbol', 'B')})",
            f"Cambiar tagline (actual: {brand.get('tagline', 'Conversacion equipada')})",
        ]
        idx = self._navigate("Version y branding", labels)
        if idx is None or idx == 0:
            return True
        if idx == 1:
            try:
                val = input(R.accent("Nueva version: ")).strip()
            except (EOFError, KeyboardInterrupt):
                return True
            if val:
                cfg["version"] = val
                self._ui_save_config(cfg)
                print(R.ok(f"✓ Version = {val}. Recarga la UI."))
        elif idx == 2:
            try:
                val = input(R.accent("Nuevo nombre de marca: ")).strip()
            except (EOFError, KeyboardInterrupt):
                return True
            if val:
                cfg.setdefault("brand", {})["name"] = val
                self._ui_save_config(cfg)
                print(R.ok(f"✓ Marca = {val}. Recarga la UI."))
        elif idx == 3:
            try:
                val = input(R.accent("Nuevo simbolo (1-2 caracteres): ")).strip()
            except (EOFError, KeyboardInterrupt):
                return True
            if val:
                cfg.setdefault("brand", {})["symbol"] = val
                self._ui_save_config(cfg)
                print(R.ok(f"✓ Simbolo = {val}. Recarga la UI."))
        elif idx == 4:
            try:
                val = input(R.accent("Nueva tagline: ")).strip()
            except (EOFError, KeyboardInterrupt):
                return True
            if val:
                cfg.setdefault("brand", {})["tagline"] = val
                self._ui_save_config(cfg)
                print(R.ok(f"✓ Tagline = {val}. Recarga la UI."))
        return True

    def _inventory_wizard(self) -> bool:
        if not self._wizard_tty_ok("/inventory"):
            return True
        from repl_inventory import gather_usable_inventory, format_usable_summary, format_category_lines, INVENTORY_CATEGORIES
        data = gather_usable_inventory()
        if not data["summary"]["total"]:
            print(R.warn("No hay piezas usables registradas."))
            return True
        while True:
            cat_labels = []
            for cat_id, cat_name, cat_desc in INVENTORY_CATEGORIES:
                count = len(data.get(cat_id, []))
                cat_labels.append(f"{cat_name}  ·  {count} piezas  —  {cat_desc}")
            cat_labels.append("Salir")
            idx = self._navigate(
                f"Inventario usable  ·  {format_usable_summary(data)}",
                cat_labels,
            )
            if idx is None or idx == len(cat_labels) - 1:
                print(R.dim("Inventario cerrado."))
                return True
            cat_id, cat_name, _ = INVENTORY_CATEGORIES[idx]
            item_lines = format_category_lines(data, cat_id)
            if not item_lines:
                print(R.warn(f"No hay piezas en '{cat_name}'."))
                continue
            sub_idx = self._navigate(f"{cat_name}  ·  {len(item_lines)} piezas", item_lines)
            if sub_idx is None:
                continue
        return True
