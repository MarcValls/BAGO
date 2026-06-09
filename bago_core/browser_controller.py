#!/usr/bin/env python3
"""BAGO Playwright Persistent Browser Controller.

Mantiene una instancia de navegador viva entre comandos para automatización
web persistente. Expone comandos de alto nivel (open, snapshot, click, fill,
screenshot, etc.) y puede registrarse como tool para el LLM.
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


@dataclass
class BrowserState:
    url: str = ""
    title: str = ""
    snapshot_text: str = ""
    element_map: dict[str, str] = field(default_factory=dict)


class BrowserController:
    """Controlador persistente de navegador via Playwright."""

    def __init__(self, headless: bool = True, viewport: dict | None = None):
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 720}
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self.state = BrowserState()
        self._closed = True

    # ── Lifecycle ────────────────────────────────────────────────────

    def ensure_open(self) -> Page:
        if self._page and not self._closed:
            return self._page
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            viewport=self.viewport,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(30000)
        self._closed = False
        return self._page

    @staticmethod
    def _url_allowed(url: str) -> bool:
        parsed = urlparse(str(url or ""))
        return parsed.scheme in {"http", "https", "file", "about"}

    def close(self) -> None:
        self._closed = True
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None
        self.state = BrowserState()

    # ── Navigation ─────────────────────────────────────────────────────

    def open(self, url: str) -> str:
        if not self._url_allowed(url):
            raise ValueError("URL no permitida. Usa http, https, file o about.")
        page = self.ensure_open()
        page.goto(url, wait_until="networkidle")
        self.state.url = page.url
        self.state.title = page.title()
        return f"Opened {url} — {self.state.title}"

    def go_back(self) -> str:
        page = self.ensure_open()
        page.go_back(wait_until="networkidle")
        self.state.url = page.url
        self.state.title = page.title()
        return f"Back to {page.url}"

    def go_forward(self) -> str:
        page = self.ensure_open()
        page.go_forward(wait_until="networkidle")
        self.state.url = page.url
        self.state.title = page.title()
        return f"Forward to {page.url}"

    def reload(self) -> str:
        page = self.ensure_open()
        page.reload(wait_until="networkidle")
        return f"Reloaded {page.url}"

    # ── Snapshot / element map ─────────────────────────────────────────

    def snapshot(self) -> str:
        page = self.ensure_open()
        self.state.url = page.url
        self.state.title = page.title()

        elements = page.query_selector_all(
            "a, button, input, textarea, select, [role='button'], [onclick]"
        )
        lines: list[str] = [f"=== {self.state.title} ===", f"URL: {self.state.url}", ""]
        element_map: dict[str, str] = {}

        for idx, el in enumerate(elements, start=1):
            ref = f"e{idx}"
            try:
                tag = el.evaluate("el => el.tagName.toLowerCase()")
                text = (el.text_content() or "").strip()[:60]
                placeholder = el.get_attribute("placeholder") or ""
                el_type = el.get_attribute("type") or ""
                name = el.get_attribute("name") or ""
                href = el.get_attribute("href") or ""

                desc_parts = [f"[{ref}] <{tag}"]
                if el_type:
                    desc_parts.append(f" type={el_type}")
                if name:
                    desc_parts.append(f" name={name}")
                if placeholder:
                    desc_parts.append(f" placeholder={placeholder}")
                desc_parts.append(">")
                if text:
                    desc_parts.append(f" {text}")
                if href:
                    desc_parts.append(f" ({href})")

                desc = "".join(desc_parts)
                lines.append(desc)
                # XPath fallback para robustez
                xpath = page.evaluate(
                    """el => {
                        const idx = (sib) => Array.from(sib.parentNode.children).indexOf(sib) + 1;
                        const segs = el => {
                            if (!el || el.nodeType !== 1) return [''];
                            return [...segs(el.parentNode), `${el.tagName.toLowerCase()}[${idx(el)}]`];
                        };
                        return segs(el).join('/');
                    }""",
                    el,
                )
                element_map[ref] = xpath
            except Exception:
                continue

        self.state.element_map = element_map
        self.state.snapshot_text = "\n".join(lines)
        return self.state.snapshot_text

    def _resolve(self, ref: str) -> str:
        if ref in self.state.element_map:
            return self.state.element_map[ref]
        # fallback: try ref as raw selector
        return ref

    # ── Interaction ──────────────────────────────────────────────────

    def click(self, ref: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.click(sel)
        return f"Clicked {ref}"

    def fill(self, ref: str, text: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.fill(sel, text)
        return f"Filled {ref} with '{text}'"

    def type(self, ref: str, text: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.type(sel, text)
        return f"Typed '{text}' into {ref}"

    def press(self, key: str) -> str:
        page = self.ensure_open()
        page.keyboard.press(key)
        return f"Pressed {key}"

    def select(self, ref: str, value: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.select_option(sel, value)
        return f"Selected {value} in {ref}"

    def hover(self, ref: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.hover(sel)
        return f"Hovered {ref}"

    def check(self, ref: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.check(sel)
        return f"Checked {ref}"

    def uncheck(self, ref: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.uncheck(sel)
        return f"Unchecked {ref}"

    def upload(self, ref: str, file_path: str) -> str:
        page = self.ensure_open()
        sel = self._resolve(ref)
        page.set_input_files(sel, file_path)
        return f"Uploaded {file_path} to {ref}"

    # ── Evaluation / extraction ──────────────────────────────────────

    def eval(self, expression: str, ref: str | None = None) -> str:
        page = self.ensure_open()
        if ref:
            sel = self._resolve(ref)
            el = page.query_selector(sel)
            if not el:
                return f"Error: element {ref} not found"
            result = page.evaluate(expression, el)
        else:
            result = page.evaluate(expression)
        return str(result)

    # ── Artifacts ────────────────────────────────────────────────────

    def screenshot(self, ref: str | None = None, output_path: str | None = None) -> str:
        page = self.ensure_open()
        path = output_path or f"browser_screenshot_{int(time.time())}.png"
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if ref:
            sel = self._resolve(ref)
            el = page.query_selector(sel)
            if el:
                el.screenshot(path=str(p))
            else:
                return f"Error: element {ref} not found"
        else:
            page.screenshot(path=str(p), full_page=True)
        return f"Screenshot saved to {p.resolve()}"

    def pdf(self, output_path: str | None = None) -> str:
        page = self.ensure_open()
        path = output_path or f"browser_page_{int(time.time())}.pdf"
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        page.pdf(path=str(p))
        return f"PDF saved to {p.resolve()}"

    def console_logs(self, level: str = "all") -> str:
        page = self.ensure_open()
        logs = []
        # Playwright no expone logs históricos fácilmente; usamos event listener
        collected: list[str] = []

        def handler(msg):
            if level == "all" or msg.type == level:
                collected.append(f"[{msg.type}] {msg.text}")

        page.on("console", handler)
        # Dar un momento para capturar logs en curso
        page.wait_for_timeout(500)
        page.remove_listener("console", handler)
        return "\n".join(collected) or "No console logs captured."

    # ── URL / info ───────────────────────────────────────────────────

    def url(self) -> str:
        page = self.ensure_open()
        return page.url

    def title(self) -> str:
        page = self.ensure_open()
        return page.title()

    # ── LLM tool helpers ─────────────────────────────────────────────

    def to_tools(self) -> list[dict[str, Any]]:
        """Exporta definiciones de herramientas OpenAI para el LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "browser_open",
                    "description": "Abre una URL en el navegador persistente.",
                    "parameters": {
                        "type": "object",
                        "properties": {"url": {"type": "string", "description": "URL a abrir"}},
                        "required": ["url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_snapshot",
                    "description": "Captura un snapshot del DOM con refs interactivos.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_click",
                    "description": "Hace click en un elemento por ref (ej. e3).",
                    "parameters": {
                        "type": "object",
                        "properties": {"ref": {"type": "string", "description": "Referencia del elemento, ej. e3"}},
                        "required": ["ref"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_fill",
                    "description": "Rellena un campo de texto por ref.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "ref": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["ref", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "browser_screenshot",
                    "description": "Captura pantalla del navegador.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "output_path": {"type": "string", "description": "Ruta opcional para guardar la imagen"},
                        },
                    },
                },
            },
        ]

    def run_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Ejecuta una herramienta LLM por nombre."""
        if name == "browser_open":
            return self.open(arguments["url"])
        if name == "browser_snapshot":
            return self.snapshot()
        if name == "browser_click":
            return self.click(arguments["ref"])
        if name == "browser_fill":
            return self.fill(arguments["ref"], arguments["text"])
        if name == "browser_screenshot":
            return self.screenshot(output_path=arguments.get("output_path"))
        return f"Unknown tool: {name}"


# ── Singleton para sesión REPL ─────────────────────────────────────

_controller: BrowserController | None = None


def get_controller(headless: bool = True) -> BrowserController:
    global _controller
    if _controller is None:
        _controller = BrowserController(headless=headless)
    return _controller


def reset_controller() -> None:
    global _controller
    if _controller:
        _controller.close()
        _controller = None
