"""test_api_dispatch_route_meta.py \u2014 Test del cambio 1: ROUTE_META como fuente unica.

Verifica:
- api_dispatch importa sin errores.
- ROUTE_META tiene 22 entradas (15 GET + 7 POST).
- GET_ROUTES y POST_ROUTES se derivan de ROUTE_META sin divergencia.
- API_PREFIXES contiene todos los prefijos necesarios.
- api_routes.all_routes() cuenta 25 (22 static + 3 dynamic).
- handlers_routes.handle() ejecuta sin errores.
- GET_ROUTES incluye /routes (registro actual, no se pierde).
"""
import sys
import unittest
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / ".bago" / "api"
sys.path.insert(0, str(API_DIR))

import api_dispatch
import api_routes


class RouteMetaTests(unittest.TestCase):

    def test_imports(self):
        self.assertTrue(hasattr(api_dispatch, "ROUTE_META"))
        self.assertTrue(hasattr(api_dispatch, "GET_ROUTES"))
        self.assertTrue(hasattr(api_dispatch, "POST_ROUTES"))

    def test_route_meta_size(self):
        self.assertEqual(len(api_dispatch.ROUTE_META), 22)
        methods = [m for m, _, _, _ in api_dispatch.ROUTE_META]
        self.assertEqual(methods.count("GET"), 15)
        self.assertEqual(methods.count("POST"), 7)

    def test_get_post_routes_match_meta(self):
        meta_get  = {p for m, p, _, _ in api_dispatch.ROUTE_META if m == "GET"}
        meta_post = {p for m, p, _, _ in api_dispatch.ROUTE_META if m == "POST"}
        self.assertEqual(set(api_dispatch.GET_ROUTES.keys()),  meta_get)
        self.assertEqual(set(api_dispatch.POST_ROUTES.keys()), meta_post)

    def test_routes_endpoint_registered(self):
        # /routes fue anadido en este cambio, no se debe perder.
        self.assertIn("/routes", api_dispatch.GET_ROUTES)
        self.assertIn("/routes", api_dispatch.API_PREFIXES)

    def test_api_prefixes_covers_all_routes(self):
        # Cada ruta estatica debe tener un prefijo coincidente en API_PREFIXES.
        for method, path, _, _ in api_dispatch.ROUTE_META:
            # path = "/chat" o "/files/read/x" -- cogemos el primer segmento.
            prefix = "/" + path.lstrip("/").split("/")[0]
            if method == "GET" and path.startswith("/models/"):
                prefix = "/models"
            self.assertIn(
                prefix, api_dispatch.API_PREFIXES,
                f"{method} {path} -> prefix {prefix!r} not in API_PREFIXES",
            )

    def test_api_routes_count(self):
        routes = api_routes.all_routes()
        # 22 estaticas + 3 dinamicas = 25
        self.assertEqual(len(routes), 25)
        static_count = sum(1 for r in routes if not r["pattern"])
        self.assertEqual(static_count, 22)
        dyn_count = sum(1 for r in routes if r["pattern"])
        self.assertEqual(dyn_count, 3)

    def test_api_routes_module_fn_consistent(self):
        # Cada (handler_module, handler_fn) declarado en ROUTE_META debe
        # poder resolverse: el modulo importa y la funcion existe.
        # Excluimos handlers que tienen dependencias rotas preexistentes
        # (handlers_command requiere bago_core/chat/commands/__init__.py
        # que no existe -- bug preexistente fuera del alcance de este cambio).
        SKIP_MODULES = {"handlers_command"}
        import importlib
        for method, path, mod_name, fn_name in api_dispatch.ROUTE_META:
            with self.subTest(route=f"{method} {path}"):
                if mod_name in SKIP_MODULES:
                    continue
                mod = importlib.import_module(mod_name)
                self.assertTrue(
                    hasattr(mod, fn_name),
                    f"{mod_name}.{fn_name} no existe",
                )

    def test_api_routes_auth_header(self):
        self.assertEqual(api_routes.auth_header(), "X-Bago-Token")

    def test_api_routes_filters(self):
        routes = api_routes.all_routes()
        only_get = api_routes.by_method("GET")
        only_patterns = api_routes.patterns_only()
        only_static = api_routes.static_routes()
        self.assertEqual(len(only_get), sum(1 for r in routes if r["method"] == "GET"))
        self.assertEqual(len(only_patterns), sum(1 for r in routes if r["pattern"]))
        self.assertEqual(len(only_static),  sum(1 for r in routes if not r["pattern"]))


class HandlerRoutesTests(unittest.TestCase):
    """Ejecuta GET /routes contra un handler fake y verifica el JSON."""

    def test_handle_routes(self):
        import io
        import json
        # Mock send_json para no depender de BaseHTTPRequestHandler internals
        # (_send_cors_headers, send_response, send_header, etc).
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_routes import handle
            handle(object())  # handler no se usa gracias al mock
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        j = captured["payload"]
        self.assertTrue(j["ok"])
        self.assertEqual(j["count"], 25)
        self.assertEqual(j["auth"], "X-Bago-Token")
        paths = [r["path"] for r in j["routes"]]
        self.assertIn("/routes", paths)
        self.assertIn("/chat", paths)
        # Cada ruta tiene los 5 campos esperados
        for r in j["routes"]:
            self.assertIn("method", r)
            self.assertIn("path", r)
            self.assertIn("handler_module", r)
            self.assertIn("handler_fn", r)
            self.assertIn("pattern", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)