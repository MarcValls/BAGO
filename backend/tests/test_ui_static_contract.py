from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI_SRC = ROOT.parent / "frontend" / "src"
ALLOWED_Z_INDEX = {30, 45, 50, 100}


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def channel_luminance(value: float) -> float:
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def contrast_ratio(fg: str, bg: str) -> float:
    fr, fg_green, fb = [channel_luminance(v) for v in hex_to_rgb(fg)]
    br, bg_green, bb = [channel_luminance(v) for v in hex_to_rgb(bg)]
    fg_lum = 0.2126 * fr + 0.7152 * fg_green + 0.0722 * fb
    bg_lum = 0.2126 * br + 0.7152 * bg_green + 0.0722 * bb
    high, low = max(fg_lum, bg_lum), min(fg_lum, bg_lum)
    return (high + 0.05) / (low + 0.05)


class UiStaticContractTests(unittest.TestCase):
    def _all_css(self) -> str:
        """Concatenate all CSS files under frontend/src/styles/ (or fall back to styles.css)."""
        styles_dir = UI_SRC / "styles"
        if styles_dir.is_dir():
            return "\n".join(p.read_text(encoding="utf-8") for p in sorted(styles_dir.rglob("*.css")))
        return (UI_SRC / "styles.css").read_text(encoding="utf-8")

    def root_tokens(self) -> dict[str, str]:
        text = self._all_css()
        return dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})", text))

    def test_text_2_contrast_uses_actual_css_token(self) -> None:
        tokens = self.root_tokens()
        for background in ["--bg", "--bg-soft", "--surface", "--surface-2"]:
            ratio = contrast_ratio(tokens["--text-2"], tokens[background])
            self.assertGreaterEqual(ratio, 4.5, f"--text-2/{background} ratio={ratio:.2f}")

    def test_z_index_values_stay_on_declared_layers(self) -> None:
        found: list[tuple[Path, int]] = []
        for path in UI_SRC.rglob("*.css"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"z-index:\s*(-?\d+)", text):
                found.append((path, int(match.group(1))))

        bad = [(str(path.relative_to(UI_SRC)), value) for path, value in found if value not in ALLOWED_Z_INDEX]
        self.assertFalse(bad, bad)

    def test_api_token_is_session_only(self) -> None:
        client = (UI_SRC / "api" / "client.ts").read_text(encoding="utf-8")
        store = (UI_SRC / "state" / "uiStore.ts").read_text(encoding="utf-8")

        self.assertNotIn("VITE_BAGO_TOKEN", client)
        self.assertNotIn("localStorage.setItem(STORAGE_TOKEN", client)
        self.assertIn("Omit<UiState, 'apiToken'>", store)
        self.assertNotIn("apiToken: state.apiToken", store)
        self.assertIn("apiToken: _legacyApiToken", store)

    def test_chat_composer_exposes_real_session_model_selector(self) -> None:
        chat = (UI_SRC / "layout" / "ChatPanel.tsx").read_text(encoding="utf-8")
        control_plane = (UI_SRC / "app" / "ControlPlane.tsx").read_text(encoding="utf-8")
        sections = (UI_SRC / "features" / "sections.tsx").read_text(encoding="utf-8")

        self.assertIn('aria-label="Modelo de esta sesión"', chat)
        self.assertIn("props.onSetSessionModel(nextModel)", chat)
        self.assertIn("Automático · router", chat)
        self.assertIn("r?.session_model", control_plane)
        self.assertNotIn("const m = r?.model", control_plane)
        self.assertIn("if (policyEntries.length > 0) return policyEntries", sections)
        self.assertNotIn("policy?.entries || props.router?.list?.entries", sections)

    def test_context_flow_has_numbered_navigation_and_visible_stage_heading(self) -> None:
        nav = (UI_SRC / "lib" / "flow-shell" / "FlowNav.tsx").read_text(encoding="utf-8")
        stage = (UI_SRC / "lib" / "flow-shell" / "FlowStageScreen.tsx").read_text(encoding="utf-8")
        styles = self._all_css()

        self.assertIn("context-flow-nav-index", nav)
        self.assertIn("aria-current={stage.id === props.activeStage ? 'step' : undefined}", nav)
        self.assertIn("context-flow-screen-header", stage)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr)", styles)


if __name__ == "__main__":
    unittest.main()
