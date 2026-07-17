"""test_api_dispatch_route_meta.py \u2014 Test del cambio 1: ROUTE_META como fuente unica.

Verifica:
- api_dispatch importa sin errores.
- ROUTE_META tiene 26 entradas (17 GET + 9 POST).
- GET_ROUTES y POST_ROUTES se derivan de ROUTE_META sin divergencia.
- API_PREFIXES contiene todos los prefijos necesarios.
- api_routes.all_routes() cuenta 29 (26 static + 3 dynamic).
- handlers_routes.handle() ejecuta sin errores.
- GET_ROUTES incluye /routes (registro actual, no se pierde).
"""
import unittest

import api_dispatch
import api_routes


class RouteMetaTests(unittest.TestCase):

    def test_imports(self):
        self.assertTrue(hasattr(api_dispatch, "ROUTE_META"))
        self.assertTrue(hasattr(api_dispatch, "GET_ROUTES"))
        self.assertTrue(hasattr(api_dispatch, "POST_ROUTES"))

    def test_route_meta_size(self):
        self.assertGreaterEqual(len(api_dispatch.ROUTE_META), 31)
        methods = [m for m, _, _, _ in api_dispatch.ROUTE_META]
        self.assertGreaterEqual(methods.count("GET"), 22)
        self.assertGreaterEqual(methods.count("POST"), 9)

    def test_get_post_routes_match_meta(self):
        meta_get  = {p for m, p, _, _ in api_dispatch.ROUTE_META if m == "GET"}
        meta_post = {p for m, p, _, _ in api_dispatch.ROUTE_META if m == "POST"}
        self.assertEqual(set(api_dispatch.GET_ROUTES.keys()),  meta_get)
        self.assertEqual(set(api_dispatch.POST_ROUTES.keys()), meta_post)

    def test_routes_endpoint_registered(self):
        # /routes fue anadido en este cambio, no se debe perder.
        self.assertIn("/routes", api_dispatch.GET_ROUTES)
        self.assertIn("/routes", api_dispatch.API_PREFIXES)
        self.assertIn("/interpret/history", api_dispatch.GET_ROUTES)
        self.assertIn("/interpret/rules", api_dispatch.GET_ROUTES)
        self.assertIn("/interpret", api_dispatch.POST_ROUTES)
        self.assertIn("/interpret", api_dispatch.API_PREFIXES)

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
        static_count = sum(1 for r in routes if not r["pattern"])
        dyn_count = sum(1 for r in routes if r["pattern"])
        self.assertEqual(static_count + dyn_count, len(routes))
        self.assertEqual(static_count, len(api_dispatch.ROUTE_META))
        self.assertGreaterEqual(dyn_count, 1)

    def test_api_routes_module_fn_consistent(self):
        # Cada (handler_module, handler_fn) declarado en ROUTE_META debe
        # poder resolverse: el modulo importa y la funcion existe.
        import importlib
        for method, path, mod_name, fn_name in api_dispatch.ROUTE_META:
            with self.subTest(route=f"{method} {path}"):
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
        self.assertEqual(j["count"], len(api_routes.all_routes()))
        self.assertEqual(j["auth"], "X-Bago-Token")
        paths = [r["path"] for r in j["routes"]]
        self.assertIn("/health", paths)
        self.assertIn("/routes", paths)
        self.assertIn("/chat", paths)
        self.assertIn("/interpret", paths)
        self.assertIn("/interpret/history", paths)
        self.assertIn("/interpret/rules", paths)
        # Cada ruta tiene los 5 campos esperados
        for r in j["routes"]:
            self.assertIn("method", r)
            self.assertIn("path", r)
            self.assertIn("handler_module", r)
            self.assertIn("handler_fn", r)
            self.assertIn("pattern", r)

    def test_handle_session_exposes_binding(self):
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        class FakeMgr:
            session_id = "sid-1"
            provider = "ollama-local"
            model = "llama3.2:3b"
            config = {"features": {"tool_calling": True}, "model_catalog": {"mode": "strict"}}

            def status(self):
                return {
                    "session_id": self.session_id,
                    "provider": self.provider,
                    "model": self.model,
                    "workspace_state_root": "C:/ws",
                    "authorized_root": "C:/ws",
                    "repo_root": "C:/repo",
                    "repo_branch": "main",
                    "objective": "keep it real",
                    "context_revision": "abc123",
                    "active_agent": "main",
                    "active_bridges": ["ollama-local"],
                    "health": {"ok": True, "detail": "ok", "latency_ms": 1.0},
                    "messages": 2,
                    "total_tokens": 10,
                    "total_calls": 1,
                    "created_at": 1.0,
                    "last_switch_at": None,
                    "switches": 0,
                    "last_receipt": {"envelope_id": "abc123"},
                    "context_measure": {
                        "ok": True,
                        "workspace_state_root": "C:/ws",
                        "provider": self.provider,
                        "model": self.model,
                        "session_id": self.session_id,
                        "history_messages": 2,
                        "tools_count": 0,
                        "model_context_tokens": 4096,
                        "binding": {"binding_confirmed": True, "binding_reason": "ok"},
                        "budget": {"available_tokens": 2048},
                    },
                }

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_session import handle

            class FakeHandler:
                session_mgr = FakeMgr()

            handle(FakeHandler())
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        payload = captured["payload"]
        self.assertEqual(payload["binding"]["workspace_state_root"], "C:/ws")
        self.assertEqual(payload["binding"]["repo_branch"], "main")
        self.assertEqual(payload["binding"]["context_revision"], "abc123")
        self.assertEqual(payload["status"]["context_measure"]["budget"]["available_tokens"], 2048)
        self.assertEqual(payload["active_agent"], "main")

    def test_handle_chat_exposes_context_receipt(self):
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        class FakeReceipt:
            def to_dict(self):
                return {"envelope_id": "env-1", "usage": {"total_tokens": 12}}

        class FakeStore:
            def get_history(self):
                return [{"role": "user", "content": "hi"}]

        class FakeMgr:
            session_id = "sid-2"
            provider = "ollama-local"
            model = "llama3.2:3b"
            last_receipt = FakeReceipt()
            store = FakeStore()

            def send(self, message):
                return "ok"

            def status(self):
                return {
                    "session_id": self.session_id,
                    "provider": self.provider,
                    "model": self.model,
                    "workspace_state_root": "C:/ws",
                    "authorized_root": "C:/ws",
                    "repo_root": "C:/repo",
                    "repo_branch": "dev",
                    "objective": "",
                    "context_revision": "env-1",
                    "active_agent": "main",
                    "active_bridges": ["ollama-local"],
                    "health": {"ok": True, "detail": "ok", "latency_ms": 1.0},
                    "messages": 1,
                    "total_tokens": 12,
                    "total_calls": 1,
                    "created_at": 1.0,
                    "last_switch_at": None,
                    "switches": 0,
                    "last_receipt": self.last_receipt.to_dict(),
                }

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_chat import handle

            class FakeHandler:
                session_mgr = FakeMgr()
                headers = {}

            handle(FakeHandler(), {"message": "hola"})
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        payload = captured["payload"]
        self.assertEqual(payload["context_receipt"]["envelope_id"], "env-1")
        self.assertEqual(payload["binding"]["repo_branch"], "dev")
        self.assertEqual(payload["binding"]["context_revision"], "env-1")

    def test_handle_chat_rejects_whitespace_message(self):
        import request_context
        original = request_context.send_json
        captured = {}

        class FakeMgr:
            session_id = "sid-3"
            provider = "ollama-local"
            model = "llama3.2:3b"
            send_called = False

            def send(self, message):
                self.send_called = True
                return "ok"

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        request_context.send_json = fake_send_json
        try:
            from handlers_chat import handle

            class FakeHandler:
                session_mgr = FakeMgr()
                headers = {}

            handler = FakeHandler()
            handle(handler, {"message": "   "})
        finally:
            request_context.send_json = original

        self.assertEqual(captured["status"], 400)
        self.assertEqual(captured["payload"]["error"], "Campo 'message' requerido")
        self.assertFalse(handler.session_mgr.send_called)

    def test_handle_chat_stream_rejects_whitespace_message(self):
        import io

        class FakeMgr:
            session_id = "sid-4"
            provider = "ollama-local"
            model = "llama3.2:3b"
            send_called = False

            def send_stream(self, message):
                self.send_called = True
                yield "ok"

        class FakeHandler:
            session_mgr = FakeMgr()
            headers = {}

            def __init__(self):
                self.status = None
                self.sent_headers = []
                self.wfile = io.BytesIO()

            def send_response(self, status):
                self.status = status

            def send_header(self, key, value):
                self.sent_headers.append((key, value))

            def end_headers(self):
                pass

        from handlers_chat_stream import handle

        handler = FakeHandler()
        handle(handler, {"message": "\n\t "})

        self.assertEqual(handler.status, 400)
        self.assertIn("Campo 'message' requerido", handler.wfile.getvalue().decode("utf-8"))
        self.assertFalse(handler.session_mgr.send_called)

    def test_handle_interpret_post_returns_backend_contract(self):
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        class FakeMgr:
            session_id = "sid-reflex"
            provider = "ollama-local"
            model = "llama3.2:3b"

            def analyze_reflexive_turn(self, text):
                return {
                    "question_id": "Q-API",
                    "literal_reading": text,
                    "intent": "formalizar",
                    "operational_intent": "work",
                    "data": [],
                    "unknowns": [],
                    "context_factors": [],
                    "restrictions": [],
                    "assumptions": [],
                    "alternatives": [],
                    "selected_interpretation": {"summary": "s", "reason": "r", "confidence": 0.9},
                    "formalization": {"schema": "Q = D + X + C + R + O", "objective": "formalizar"},
                    "evidence": [],
                    "audit_trail": [],
                    "self_reference": {"detected": True, "depth": 1},
                    "fixed_point": {"condition": "F(R*) ~= R*", "stable": True},
                    "metrics": {"fidelity": 0.9, "traceability": 0.8, "ambiguity": 0.0},
                    "limits": [],
                    "confidence": 0.9,
                }

            def record_reflexive_command_audit(self, *, analysis, response_content, command):
                return {"audit_id": "RA-API", "path": "x.jsonl", "question_id": analysis["question_id"]}

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_interpret import handle_post

            class FakeHandler:
                session_mgr = FakeMgr()

            handle_post(FakeHandler(), {"question": "Como formalizo esto?"})
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        payload = captured["payload"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["analysis"]["question_id"], "Q-API")
        self.assertEqual(payload["audit"]["audit_id"], "RA-API")
        self.assertIn("INTERPRETE REFLEXIVO", payload["report"])

    def test_handle_interpret_history_returns_audit_tail(self):
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        class FakeMgr:
            session_id = "sid-reflex"
            provider = "ollama-local"
            model = "llama3.2:3b"

            def reflexive_audit_tail(self, limit):
                return {
                    "ok": True,
                    "path": "state/evidence/reflexive_interpretations.jsonl",
                    "count": 1,
                    "items": [{"audit_id": "RA-1", "intent": "formalizar"}],
                    "limit_seen": limit,
                }

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_interpret import handle_history

            class FakeHandler:
                session_mgr = FakeMgr()
                path = "/interpret/history?limit=7"

            handle_history(FakeHandler())
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        payload = captured["payload"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["limit_seen"], 7)
        self.assertEqual(payload["items"][0]["audit_id"], "RA-1")

    def test_handle_interpret_rules_returns_rules_contract(self):
        import api_serializers
        original = api_serializers.send_json
        captured = {}

        def fake_send_json(handler, status, payload):
            captured["status"] = status
            captured["payload"] = payload

        api_serializers.send_json = fake_send_json
        try:
            from handlers_interpret import handle_rules
            handle_rules(object())
        finally:
            api_serializers.send_json = original

        self.assertEqual(captured["status"], 200)
        payload = captured["payload"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rules"]["contract_version"], "bago.reflexive.rules.v1")
        self.assertEqual(payload["rules"]["source"], "file")
        self.assertTrue(payload["rules"]["validation"]["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
