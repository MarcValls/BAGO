#!/usr/bin/env python3
"""Menu y asistentes del REPL de BAGO, extraidos de repl.py."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import renderer as R
from commands import MENU_SECTIONS
from switch_engine import SwitchEngine


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


class BagoReplMenuMixin:
    def _command_catalog(self) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        for section in MENU_SECTIONS:
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
        while True:
            labels = [f"{section['title']}  —  {section['description']}" for section in MENU_SECTIONS]
            idx = self._navigate("Menu de funciones", labels)
            if idx is None:
                print(R.dim("Menu cerrado."))
                return True
            section = MENU_SECTIONS[idx]
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
        if name == "credentials":
            return self._credential_wizard()
        if name == "switch":
            return self._switch_wizard()
        if name == "agent":
            return self._agent_wizard()
        if name == "load":
            return self._load_wizard()
        if name == "feedback":
            return self._feedback_wizard()
        if name == "tools":
            return self._tools_wizard()
        if name == "memory-delete":
            return self._memory_delete_wizard()
        if name == "project":
            return self._project_wizard(Path(self.mgr.base_path))
        if name == "config":
            return self._config_wizard()
        if name == "ui":
            return self._ui_wizard()
        print(R.error(f"Asistente desconocido: {name}"))
        return True

    def _wizard_tty_ok(self, manual_hint: str) -> bool:
        if sys.stdin.isatty() and sys.stdout.isatty():
            return True
        print(R.warn(f"El asistente requiere un terminal interactivo. Usa: {manual_hint}"))
        return False

    def _switch_wizard(self) -> bool:
        if not self._wizard_tty_ok("/switch <provider> [modelo]"):
            return True
        try:
            providers = self.mgr.available_providers()
        except Exception as exc:
            print(R.error(f"No se pudieron listar los providers: {exc}"))
            return True
        if not providers:
            print(R.warn("No hay providers registrados."))
            return True

        plabels = []
        for p in providers:
            estado = "✓" if p.get("configured") else "○"
            nmod = len(p.get("models") or [])
            plabels.append(f"{estado} {p['name']}  ·  {nmod} modelos")
        pidx = self._navigate("Cambiar provider · elige uno", plabels)
        if pidx is None:
            print(R.dim("Asistente cerrado."))
            return True
        provider = providers[pidx]["name"]

        if not providers[pidx].get("configured", False):
            print(R.warn(f"'{provider}' no tiene credenciales."))
            if not self._credential_wizard_provider(provider):
                return True
            if self.mgr.provider != provider:
                print(R.error("No se pudo conectar."))
                return True
            print(R.ok(f"✓ Conectado a {provider}/{self.mgr.model}"))
            self.engine = SwitchEngine(self.mgr.adapters)
            return True

        try:
            catalog = self.mgr.list_model_catalog(provider)
        except Exception:
            catalog = []
        model = None
        if catalog:
            mlabels = ["(auto)"] + [str(item["id"]) for item in catalog]
            midx = self._navigate(f"{provider} · modelo", mlabels)
            if midx is None:
                return True
            if midx > 0:
                model = catalog[midx - 1]["id"]

        result = self.mgr.switch(provider, model, force=True)
        if result.get("ok"):
            print(R.ok(f"✓ Conectado a {provider}/{self.mgr.model}"))
            self.engine = SwitchEngine(self.mgr.adapters)
        else:
            err = result.get("error") or result.get("warnings", ["?"])[0]
            print(R.error(f"✗ {err}"))
        return True

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
        labels = [
            f"Analizar directorio actual ({project_root.name})",
            "Ver estado del proyecto",
            "Inicializar estructura .bago",
            "Vincular proyecto portable",
            "Seguir con la sesión",
        ]
        idx = self._navigate(f"Proyecto detectado · {project_root}", labels)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        mod = _load_tool_module("project_memory", "project_memory.py")
        if idx == 0:
            data = mod.analyze_data(project_root)
            print(mod.format_analysis(data))
            return True
        if idx == 1:
            data = mod.status_data(project_root)
            print(mod.format_status(data))
            return True
        if idx == 2:
            data = mod.init_project(project_root)
            print(R.ok(f"Proyecto inicializado: {data['bago_dir']}"))
            return True
        if idx == 3:
            data = mod.link_project(project_root)
            print(R.ok(f"Proyecto vinculado: {data['root']} ({data['link_mode']})"))
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
        if not self._wizard_tty_ok("/tools [enable|disable]"):
            return True
        cur = bool(self.mgr.config.get("features.tool_calling", False))
        idx = self._navigate(
            f"Herramientas del modelo (actual: {'activadas' if cur else 'desactivadas'})",
            ["Activar herramientas", "Desactivar herramientas", "Listar herramientas"],
        )
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        return self._handle_command(["/tools enable", "/tools disable", "/tools list"][idx])

    def _memory_delete_wizard(self) -> bool:
        if not self._wizard_tty_ok("/memory delete <id>"):
            return True
        try:
            recent = self.mgr.knowledge.list_recent(limit=20)
        except Exception as exc:
            print(R.error(f"No se pudieron listar los recuerdos: {exc}"))
            return True
        if not recent:
            print(R.warn("No hay recuerdos almacenados."))
            return True
        labels = []
        for r in recent:
            when = str(r.get("created_at", ""))[:19]
            content = str(r.get("content", "")).replace("\n", " ")[:50]
            labels.append(f"{r.get('id', '?')}  ·  {when}  ·  {content}")
        idx = self._navigate("Eliminar recuerdo · elige uno", labels)
        if idx is None:
            print(R.dim("Asistente cerrado."))
            return True
        return self._handle_command(f"/memory delete {recent[idx]['id']}")

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
