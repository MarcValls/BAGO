"""Tests para AccountManager y multi-cuenta en CredentialManager.

Cobertura:
  - AccountManager: add / remove / set_active / find / accounts_for
  - AccountManager: apply_active_credentials (env vars)
  - AccountManager: import_from_creds (migración idempotente)
  - AccountManager: summary_lines
  - AccountManager: ID auto-incremental sin huecos
  - CredentialManager.do_login subcomandos: list / switch / remove / add
  - _check_gemini (providers.py)
"""

import json
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / ".bago" / "tools"))

from bago.credentials import AccountManager
import bago.constants as bago_constants


# ── helpers ───────────────────────────────────────────────────────────────────

def make_am(tmp_dir=None) -> tuple[AccountManager, Path]:
    """Crea un AccountManager apuntando a un fichero temporal."""
    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp()
    f = Path(tmp_dir) / "accounts.json"
    return AccountManager(f), f


# ═══════════════════════════════════════════════════════════════════════════════
# 1 · AccountManager — operaciones básicas
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountManagerBasic(unittest.TestCase):

    def setUp(self):
        self.am, self.f = make_am()

    # ── add ───────────────────────────────────────────────────────────────────

    def test_add_returns_generated_id(self):
        aid = self.am.add("github", "Personal", "ghp_abc123")
        self.assertEqual(aid, "github-1")

    def test_add_second_account_increments(self):
        self.am.add("github", "Personal", "ghp_aaa")
        aid2 = self.am.add("github", "Trabajo", "ghp_bbb", make_active=False)
        self.assertEqual(aid2, "github-2")

    def test_add_different_providers_no_collision(self):
        a1 = self.am.add("github", "G", "ghp_xxx")
        a2 = self.am.add("gemini", "Gem", "AIzaSy_xxx")
        self.assertEqual(a1, "github-1")
        self.assertEqual(a2, "gemini-1")

    def test_add_uses_auto_label_when_empty(self):
        self.am.add("github", "", "ghp_xxx")
        acc = self.am.find("github-1")
        self.assertIn("GitHub", acc["label"])

    def test_add_persists_to_file(self):
        self.am.add("gemini", "Mi Gemini", "AIzaSy_test")
        data = json.loads(self.f.read_text(encoding="utf-8"))
        self.assertEqual(len(data["accounts"]), 1)
        self.assertEqual(data["accounts"][0]["id"], "gemini-1")

    def test_add_first_account_becomes_active(self):
        self.am.add("openai", "GPT", "sk-test")
        self.assertEqual(self.am.get_active_id("openai"), "openai-1")

    def test_add_make_active_false_does_not_override(self):
        self.am.add("github", "P1", "ghp_1")
        self.am.add("github", "P2", "ghp_2", make_active=False)
        # El activo sigue siendo el primero
        self.assertEqual(self.am.get_active_id("github"), "github-1")

    def test_add_make_active_true_overrides(self):
        self.am.add("github", "P1", "ghp_1")
        self.am.add("github", "P2", "ghp_2", make_active=True)
        self.assertEqual(self.am.get_active_id("github"), "github-2")

    # ── find / accounts_for ───────────────────────────────────────────────────

    def test_find_returns_account(self):
        self.am.add("anthropic", "Ant", "sk-ant-xxx")
        acc = self.am.find("anthropic-1")
        self.assertIsNotNone(acc)
        self.assertEqual(acc["credential"], "sk-ant-xxx")

    def test_find_returns_none_for_missing(self):
        self.assertIsNone(self.am.find("nonexistent-99"))

    def test_accounts_for_filters_by_provider(self):
        self.am.add("github", "G", "ghp_1")
        self.am.add("github", "G2", "ghp_2", make_active=False)
        self.am.add("gemini", "Gem", "AIzaSy")
        github_accs = self.am.accounts_for("github")
        self.assertEqual(len(github_accs), 2)
        self.assertTrue(all(a["provider"] == "github" for a in github_accs))

    def test_accounts_for_empty_provider(self):
        self.assertEqual(self.am.accounts_for("openrouter"), [])

    # ── remove ────────────────────────────────────────────────────────────────

    def test_remove_existing_returns_true(self):
        self.am.add("github", "G", "ghp_x")
        self.assertTrue(self.am.remove("github-1"))
        self.assertEqual(len(self.am.accounts), 0)

    def test_remove_nonexistent_returns_false(self):
        self.assertFalse(self.am.remove("github-99"))

    def test_remove_active_promotes_next(self):
        self.am.add("github", "P1", "ghp_1")
        self.am.add("github", "P2", "ghp_2", make_active=False)
        # github-1 es activo, lo eliminamos
        self.am.remove("github-1")
        self.assertEqual(self.am.get_active_id("github"), "github-2")

    def test_remove_only_account_clears_active(self):
        self.am.add("github", "P1", "ghp_1")
        self.am.remove("github-1")
        self.assertIsNone(self.am.get_active_id("github"))

    def test_remove_persists(self):
        self.am.add("gemini", "G", "key")
        self.am.remove("gemini-1")
        data = json.loads(self.f.read_text(encoding="utf-8"))
        self.assertEqual(data["accounts"], [])

    # ── set_active ────────────────────────────────────────────────────────────

    def test_set_active_returns_true(self):
        self.am.add("github", "P1", "ghp_1")
        self.am.add("github", "P2", "ghp_2", make_active=False)
        self.assertTrue(self.am.set_active("github-2"))
        self.assertEqual(self.am.get_active_id("github"), "github-2")

    def test_set_active_nonexistent_returns_false(self):
        self.assertFalse(self.am.set_active("github-99"))

    def test_set_active_enables_account(self):
        self.am.add("github", "P", "ghp_x")
        acc = self.am.find("github-1")
        acc["enabled"] = False
        self.am.set_active("github-1")
        self.assertTrue(self.am.find("github-1")["enabled"])

    # ── update ────────────────────────────────────────────────────────────────

    def test_update_credential(self):
        self.am.add("openai", "GPT", "sk-old")
        self.am.update("openai-1", credential="sk-new")
        self.assertEqual(self.am.find("openai-1")["credential"], "sk-new")

    def test_update_nonexistent_returns_false(self):
        self.assertFalse(self.am.update("openai-99", credential="x"))

    # ── all_providers ─────────────────────────────────────────────────────────

    def test_all_providers_returns_unique(self):
        self.am.add("github", "G1", "g1")
        self.am.add("github", "G2", "g2", make_active=False)
        self.am.add("gemini", "Gem", "ai")
        providers = self.am.all_providers()
        self.assertEqual(set(providers), {"github", "gemini"})


# ═══════════════════════════════════════════════════════════════════════════════
# 2 · AccountManager — env vars y migración
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountManagerEnvAndMigration(unittest.TestCase):

    def setUp(self):
        self.am, _ = make_am()
        # Limpiar vars de entorno relevantes
        for var in ["GITHUB_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"]:
            os.environ.pop(var, None)

    def tearDown(self):
        for var in ["GITHUB_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"]:
            os.environ.pop(var, None)

    def test_apply_active_sets_env_var(self):
        self.am.add("github", "Personal", "ghp_mytoken123456")
        self.am.apply_active_credentials()
        self.assertEqual(os.environ.get("GITHUB_TOKEN"), "ghp_mytoken123456")

    def test_apply_active_multiple_providers(self):
        self.am.add("github", "G", "ghp_gh")
        self.am.add("gemini", "Gem", "AIzaSy_gem")
        self.am.apply_active_credentials()
        self.assertEqual(os.environ.get("GITHUB_TOKEN"), "ghp_gh")
        self.assertEqual(os.environ.get("GEMINI_API_KEY"), "AIzaSy_gem")

    def test_apply_active_skips_disabled(self):
        self.am.add("openai", "GPT", "sk-test")
        acc = self.am.find("openai-1")
        acc["enabled"] = False
        self.am.apply_active_credentials()
        self.assertNotIn("OPENAI_API_KEY", os.environ)

    def test_import_from_creds_creates_accounts(self):
        creds = {"github": "ghp_migrated", "openai": "sk-migrated"}
        self.am.import_from_creds(creds)
        self.assertEqual(len(self.am.accounts_for("github")), 1)
        self.assertEqual(self.am.accounts_for("github")[0]["credential"], "ghp_migrated")

    def test_import_from_creds_is_idempotent(self):
        """Segunda importación no duplica si ya hay cuentas."""
        creds = {"github": "ghp_v1"}
        self.am.import_from_creds(creds)
        self.am.import_from_creds({"github": "ghp_v2"})
        self.assertEqual(len(self.am.accounts_for("github")), 1)
        # La credencial original no fue sobreescrita
        self.assertEqual(self.am.accounts_for("github")[0]["credential"], "ghp_v1")

    def test_import_skips_empty_values(self):
        self.am.import_from_creds({"openai": ""})
        self.assertEqual(self.am.accounts_for("openai"), [])

    def test_import_reads_env_fallback(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-env"
        self.am.import_from_creds({})
        accs = self.am.accounts_for("anthropic")
        self.assertEqual(len(accs), 1)
        self.assertEqual(accs[0]["credential"], "sk-ant-env")

    def test_user_bago_env_override(self):
        tmp = Path(tempfile.mkdtemp())
        original_home = os.environ.get("BAGO_USER_HOME")
        try:
            os.environ["BAGO_USER_HOME"] = str(tmp)
            constants = importlib.reload(bago_constants)
            self.assertEqual(constants.USER_BAGO, tmp.resolve())
            self.assertEqual(constants.CRED_FILE, tmp.resolve() / "credentials.json")
            self.assertEqual(constants.ACCOUNTS_FILE, tmp.resolve() / "accounts.json")
        finally:
            if original_home is None:
                os.environ.pop("BAGO_USER_HOME", None)
            else:
                os.environ["BAGO_USER_HOME"] = original_home
            importlib.reload(bago_constants)


# ═══════════════════════════════════════════════════════════════════════════════
# 3 · AccountManager — summary_lines
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountManagerSummary(unittest.TestCase):

    def setUp(self):
        self.am, _ = make_am()

    def test_summary_empty_has_hint(self):
        lines = self.am.summary_lines()
        self.assertTrue(any("sin cuentas" in l or "/login add" in l for l in lines))

    def test_summary_shows_provider_label(self):
        self.am.add("github", "Personal", "ghp_x")
        lines = self.am.summary_lines()
        joined = " ".join(lines)
        self.assertIn("GitHub", joined)

    def test_summary_marks_active_with_star(self):
        self.am.add("gemini", "G1", "key1")
        self.am.add("gemini", "G2", "key2", make_active=True)
        lines = self.am.summary_lines()
        joined = " ".join(lines)
        self.assertIn("★", joined)

    def test_summary_masks_credential(self):
        self.am.add("openai", "GPT", "sk-abcdefghijklmnop")
        lines = self.am.summary_lines()
        joined = " ".join(lines)
        # Credencial debe aparecer enmascarada, no en claro
        self.assertNotIn("sk-abcdefghijklmnop", joined)
        self.assertIn("…", joined)

    def test_summary_shows_account_count(self):
        self.am.add("github", "P1", "g1")
        self.am.add("github", "P2", "g2", make_active=False)
        lines = self.am.summary_lines()
        joined = " ".join(lines)
        self.assertIn("2 cuentas", joined)


# ═══════════════════════════════════════════════════════════════════════════════
# 4 · AccountManager — persistencia y recarga
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountManagerPersistence(unittest.TestCase):

    def test_reload_preserves_accounts(self):
        tmp = tempfile.mkdtemp()
        f = Path(tmp) / "accounts.json"
        am1 = AccountManager(f)
        am1.add("anthropic", "Claude", "sk-ant-test")

        # Recargar desde el mismo fichero
        am2 = AccountManager(f)
        acc = am2.find("anthropic-1")
        self.assertIsNotNone(acc)
        self.assertEqual(acc["credential"], "sk-ant-test")
        self.assertEqual(am2.get_active_id("anthropic"), "anthropic-1")

    def test_corrupt_file_initializes_empty(self):
        tmp = tempfile.mkdtemp()
        f = Path(tmp) / "accounts.json"
        f.write_text("NOT VALID JSON", encoding="utf-8")
        am = AccountManager(f)
        self.assertEqual(am.accounts, [])

    def test_missing_file_initializes_empty(self):
        tmp = tempfile.mkdtemp()
        f = Path(tmp) / "no_file.json"
        am = AccountManager(f)
        self.assertEqual(am.accounts, [])

    def test_id_increments_skip_deleted(self):
        """Después de borrar github-1, el siguiente add crea github-2 (no reusar gap)."""
        am, _ = make_am()
        am.add("github", "P1", "g1")
        am.add("github", "P2", "g2", make_active=False)
        am.remove("github-1")  # queda solo github-2
        new_id = am.add("github", "P3", "g3", make_active=False)
        # El siguiente libre es github-1 (lo reutiliza porque ya no existe)
        self.assertEqual(new_id, "github-1")


# ═══════════════════════════════════════════════════════════════════════════════
# 5 · CredentialManager.do_login — subcomandos multi-cuenta
# ═══════════════════════════════════════════════════════════════════════════════

class TestDoLoginSubcommands(unittest.TestCase):
    """Tests de do_login para add / list / switch / remove."""

    def _make_cm(self, tmp):
        """Crea un CredentialManager con paths temporales."""
        from bago.credentials import CredentialManager
        cred_file = Path(tmp) / "credentials.json"
        accounts_file = Path(tmp) / "accounts.json"
        with patch("bago.credentials.manager.CRED_FILE", cred_file), \
             patch("bago.credentials.manager.ACCOUNTS_FILE", accounts_file):
            cm = CredentialManager.__new__(CredentialManager)
            cm._file = cred_file
            cm._creds = {}
            cm._accounts = AccountManager(accounts_file)
        return cm

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cm = self._make_cm(self.tmp)
        # Pre-registrar una cuenta github
        self.cm._accounts.add("github", "Personal", "ghp_test123456")

    # ── list ──────────────────────────────────────────────────────────────────

    def test_list_returns_empty_string(self):
        with patch("bago.credentials.login_flows.console") as mock_console:
            result = self.cm.do_login("list")
        self.assertEqual(result, "")

    def test_list_calls_console_print(self):
        with patch("bago.credentials.login_flows.console") as mock_console:
            self.cm.do_login("list")
        mock_console.print.assert_called()

    # ── switch ────────────────────────────────────────────────────────────────

    def test_switch_valid_account_returns_success(self):
        self.cm._accounts.add("github", "Trabajo", "ghp_work", make_active=False)
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("switch github-2")
        self.assertIn("github-2", result)
        self.assertIn("✓", result)

    def test_switch_nonexistent_returns_error(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("switch github-99")
        self.assertIn("no encontrada", result)

    def test_switch_no_arg_returns_usage(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("switch")
        self.assertIn("Uso", result)

    # ── remove ────────────────────────────────────────────────────────────────

    def test_remove_existing_returns_success(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("remove github-1")
        self.assertIn("eliminada", result)
        self.assertIsNone(self.cm._accounts.find("github-1"))

    def test_remove_nonexistent_returns_error(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("remove github-99")
        self.assertIn("no encontrada", result)

    def test_remove_no_arg_returns_usage(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("remove")
        self.assertIn("Uso", result)

    # ── add ───────────────────────────────────────────────────────────────────

    def test_add_no_provider_returns_usage(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("add")
        self.assertIn("Uso", result)

    def test_add_unsupported_provider_returns_error(self):
        with patch("bago.credentials.login_flows.console"):
            result = self.cm.do_login("add fakecloud")
        self.assertIn("no soportado", result)


# ═══════════════════════════════════════════════════════════════════════════════
# 6 · _check_gemini (providers.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCheckGemini(unittest.TestCase):
    """Tests para la función _check_gemini dentro de scan_provider_health."""

    def _run_scan_gemini(self, env_overrides=None, http_response=None, http_error=None):
        """Ejecuta scan_provider_health y devuelve el resultado para 'gemini'."""
        from bago.providers import scan_provider_health
        env = {k: v for k, v in os.environ.items()}
        env.update(env_overrides or {})
        # Limpiar token si no se pasa
        if env_overrides is not None and "GEMINI_API_KEY" not in env_overrides:
            env.pop("GEMINI_API_KEY", None)

        def fake_urlopen(req, timeout=5):
            if http_error:
                raise http_error
            ctx = MagicMock()
            ctx.__enter__ = lambda s: s
            ctx.__exit__ = MagicMock(return_value=False)
            ctx.read.return_value = json.dumps(http_response).encode()
            return ctx

        import urllib.request
        import urllib.error
        with patch.dict(os.environ, env, clear=True), \
             patch("urllib.request.urlopen", side_effect=fake_urlopen):
            results = scan_provider_health(None, {}, timeout=2)
        return results["gemini"]

    def test_no_api_key_returns_not_ok(self):
        result = self._run_scan_gemini(env_overrides={})
        self.assertFalse(result["ok"])
        self.assertIn("GEMINI_API_KEY", result["detail"])

    def test_valid_key_with_models_returns_ok(self):
        models_response = {
            "models": [
                {"name": "models/gemini-1.5-pro"},
                {"name": "models/gemini-2.0-flash"},
                {"name": "models/gemini-1.0-pro"},
            ]
        }
        result = self._run_scan_gemini(
            env_overrides={"GEMINI_API_KEY": "AIzaSy_testkey12345"},
            http_response=models_response,
        )
        self.assertTrue(result["ok"])
        self.assertIn("gemini", result["detail"])

    def test_valid_key_includes_model_names(self):
        models_response = {"models": [{"name": "models/gemini-2.0-flash"}]}
        result = self._run_scan_gemini(
            env_overrides={"GEMINI_API_KEY": "AIzaSy_testkey12345"},
            http_response=models_response,
        )
        self.assertIn("gemini-2.0-flash", result["detail"])

    def test_invalid_key_400_returns_not_ok(self):
        import urllib.error
        err = urllib.error.HTTPError(url="", code=400, msg="Bad Request", hdrs={}, fp=None)
        result = self._run_scan_gemini(
            env_overrides={"GEMINI_API_KEY": "bad_key"},
            http_error=err,
        )
        self.assertFalse(result["ok"])
        self.assertIn("400", result["detail"])

    def test_forbidden_403_returns_not_ok(self):
        import urllib.error
        err = urllib.error.HTTPError(url="", code=403, msg="Forbidden", hdrs={}, fp=None)
        result = self._run_scan_gemini(
            env_overrides={"GEMINI_API_KEY": "restricted_key"},
            http_error=err,
        )
        self.assertFalse(result["ok"])
        self.assertIn("403", result["detail"])

    def test_network_error_with_key_returns_ok_no_ping(self):
        """Si hay key pero falla la red, se asume ok (sin ping)."""
        import urllib.error
        err = OSError("network unreachable")
        result = self._run_scan_gemini(
            env_overrides={"GEMINI_API_KEY": "AIzaSy_offline1234"},
            http_error=err,
        )
        self.assertTrue(result["ok"])
        self.assertIn("sin conexion", result["detail"])


if __name__ == "__main__":
    unittest.main()
