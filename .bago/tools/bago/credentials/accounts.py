"""AccountManager — múltiples cuentas/tokens por tipo de proveedor.

Almacena en ~/.bago/accounts.json:
{
  "accounts": [
    {"id": "github-1", "provider": "github", "label": "Personal",
     "credential_type": "token", "credential": "ghp_...",
     "enabled": true, "created_at": "2025-01-01T12:00:00"},
    ...
  ],
  "active": {"github": "github-2", "gemini": "gemini-1"}
}
"""

import json
import os
from datetime import datetime
from pathlib import Path


class AccountManager:
    """Gestiona múltiples cuentas/tokens por tipo de proveedor."""

    # tipo de provider → variable de entorno que aplica
    PROVIDER_ENV = {
        "github":       "GITHUB_TOKEN",
        "openai":       "OPENAI_API_KEY",
        "anthropic":    "ANTHROPIC_API_KEY",
        "openrouter":   "OPENROUTER_API_KEY",
        "gemini":       "GEMINI_API_KEY",
        "ollama_cloud": "OLLAMA_CLOUD_API_KEY",
    }

    PROVIDER_LABELS = {
        "github":       "GitHub (Copilot + Models)",
        "openai":       "OpenAI / ChatGPT",
        "anthropic":    "Anthropic Claude",
        "openrouter":   "OpenRouter",
        "gemini":       "Google Gemini",
        "ollama_cloud": "Ollama Cloud",
    }

    def __init__(self, accounts_file: Path):
        self._file = accounts_file
        self._data: dict = {"accounts": [], "active": {}}
        self._load()

    # ── I/O ────────────────────────────────────────────────────────────────────

    def _load(self):
        if self._file.exists():
            try:
                self._data = json.loads(self._file.read_text(encoding="utf-8"))
            except Exception:
                self._data = {"accounts": [], "active": {}}

    def _save(self):
        from ._atomic import atomic_write_json
        atomic_write_json(self._file, self._data, indent=2, ensure_ascii=False)

    # ── Queries ─────────────────────────────────────────────────────────────────

    @property
    def accounts(self) -> list:
        return self._data.get("accounts", [])

    def find(self, account_id: str) -> dict | None:
        for a in self.accounts:
            if a["id"] == account_id:
                return a
        return None

    def accounts_for(self, provider: str) -> list:
        return [a for a in self.accounts if a["provider"] == provider]

    def get_active_id(self, provider: str) -> str | None:
        return self._data.get("active", {}).get(provider)

    def get_active(self, provider: str) -> dict | None:
        aid = self.get_active_id(provider)
        return self.find(aid) if aid else None

    def all_providers(self) -> list[str]:
        """Tipos de provider con al menos una cuenta registrada."""
        return list({a["provider"] for a in self.accounts})

    # ── Mutations ───────────────────────────────────────────────────────────────

    def add(
        self,
        provider: str,
        label: str,
        credential: str,
        credential_type: str = "api_key",
        make_active: bool = True,
    ) -> str:
        """Agrega una cuenta nueva. Devuelve el ID asignado (ej: 'github-2')."""
        existing_ids = {a["id"] for a in self.accounts}
        i = 1
        while f"{provider}-{i}" in existing_ids:
            i += 1
        account_id = f"{provider}-{i}"

        auto_label = f"{self.PROVIDER_LABELS.get(provider, provider)} #{i}"
        account = {
            "id":              account_id,
            "provider":        provider,
            "label":           label or auto_label,
            "credential_type": credential_type,
            "credential":      credential,
            "enabled":         True,
            "created_at":      datetime.now().isoformat(timespec="seconds"),
        }
        self._data.setdefault("accounts", []).append(account)
        if make_active or not self.get_active_id(provider):
            self._data.setdefault("active", {})[provider] = account_id
        self._save()
        return account_id

    def update(self, account_id: str, **kwargs) -> bool:
        """Actualiza campos de una cuenta (label, credential, enabled…)."""
        acc = self.find(account_id)
        if not acc:
            return False
        for k, v in kwargs.items():
            acc[k] = v
        self._save()
        return True

    def remove(self, account_id: str) -> bool:
        """Elimina una cuenta. Si era la activa, promueve la siguiente."""
        acc = self.find(account_id)
        if not acc:
            return False
        provider = acc["provider"]
        self._data["accounts"] = [a for a in self.accounts if a["id"] != account_id]
        if self._data.get("active", {}).get(provider) == account_id:
            remaining = self.accounts_for(provider)
            if remaining:
                self._data["active"][provider] = remaining[0]["id"]
            else:
                self._data.get("active", {}).pop(provider, None)
        self._save()
        return True

    def set_active(self, account_id: str) -> bool:
        """Establece una cuenta como activa para su tipo de proveedor."""
        acc = self.find(account_id)
        if not acc:
            return False
        acc["enabled"] = True
        self._data.setdefault("active", {})[acc["provider"]] = account_id
        self._save()
        return True

    # ── Entorno ─────────────────────────────────────────────────────────────────

    def apply_active_credentials(self):
        """Aplica las credenciales activas como variables de entorno."""
        for provider, env_key in self.PROVIDER_ENV.items():
            active = self.get_active(provider)
            if active and active.get("enabled") and active.get("credential"):
                os.environ[env_key] = active["credential"]

    def import_from_creds(self, creds_dict: dict):
        """Migra credentials.json existente como cuentas base (idempotente)."""
        mapping = {
            "github":       ("github",       "GITHUB_TOKEN",        "token"),
            "openai":       ("openai",        "OPENAI_API_KEY",      "api_key"),
            "anthropic":    ("anthropic",     "ANTHROPIC_API_KEY",   "api_key"),
            "openrouter":   ("openrouter",    "OPENROUTER_API_KEY",  "api_key"),
            "ollama_cloud": ("ollama_cloud",  "OLLAMA_CLOUD_API_KEY", "api_key"),
        }
        for cred_key, (provider, env_key, ctype) in mapping.items():
            if self.accounts_for(provider):
                continue  # ya tiene cuentas — no sobreescribir
            value = creds_dict.get(cred_key) or os.environ.get(env_key, "")
            if value:
                self.add(
                    provider=provider,
                    label=f"{self.PROVIDER_LABELS.get(provider, provider)} (migrado)",
                    credential=value,
                    credential_type=ctype,
                    make_active=True,
                )

    # ── Representación ──────────────────────────────────────────────────────────

    def summary_lines(self) -> list[str]:
        """Líneas Rich para mostrar en /scan o /status."""
        if not self.accounts:
            return ["  [dim](sin cuentas registradas — usa /login add <provider>)[/dim]"]
        lines = []
        for provider in sorted(self.all_providers()):
            accs = self.accounts_for(provider)
            active_id = self.get_active_id(provider)
            plabel = self.PROVIDER_LABELS.get(provider, provider)
            lines.append(
                f"  [bold]{plabel}[/bold]  "
                f"[dim]({len(accs)} cuenta{'s' if len(accs) != 1 else ''})[/dim]"
            )
            for acc in accs:
                is_active = acc["id"] == active_id
                star = "[bold yellow]★[/bold yellow]" if is_active else "  "
                cred = acc.get("credential", "")
                masked = f"{cred[:4]}…{cred[-4:]}" if len(cred) > 8 else "●●●"
                label = acc.get("label", acc["id"])
                color = "green" if is_active and acc.get("enabled") else "dim"
                lines.append(
                    f"    {star} [{color}]{acc['id']:<16}[/{color}]"
                    f"  [{color}]{label:<28}[/{color}]"
                    f"  [dim]{masked}[/dim]"
                )
        return lines
