"""api_dispatch.py \u2014 HTTP routing for the BAGO API bridge.

Single place where `do_GET` and `do_POST` decide which handler module
runs. Handlers live in `handlers_<domain>.py` and are called as
`module.handle(self)` where `self` is the BagoAPIHandler instance.

Adding a new endpoint = adding one entry to `GET_ROUTES` or `POST_ROUTES`.
No need to edit bridge.py.

This module also defines `API_PREFIXES` (the set of paths the bridge
treats as API rather than static). Keep it in sync with the actual routes
or the 404 short-circuit in bridge.py will misbehave.
"""

from __future__ import annotations

import importlib
from typing import Callable, Tuple


def _call(mod_name: str, fn_name: str, *extra):
    """Lazy import + call. Re-imports each call so monkey-patching handlers
    in tests works without reloading the dispatch table.

    Extra positional args are passed to the handler after `handler`.
    Use this for handlers with signatures like `handle(handler, provider)`.
    """
    def _inner(handler, *args):
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        if extra:
            return fn(handler, *extra, *args)
        return fn(handler, *args)
    return _inner


def _post(mod_name: str, fn_name: str):
    """Build a POST handler closure that ignores URL/body args and calls
    `fn_name(handler, body)`. Kept as a top-level helper so _from_meta
    can reference it from below.
    """
    def _inner(handler, body):
        mod = importlib.import_module(mod_name)
        return getattr(mod, fn_name)(handler, body)
    return _inner


# Single source of truth for static routes.
# (method, path, handler_module, handler_fn). Order is preserved; route
# dispatch iterates in this order so callers see deterministic behaviour.
# Dynamic patterns are declared in DYNAMIC_ROUTE_META below. The matcher code
# remains explicit because each pattern has different validation/extraction.
ROUTE_META: tuple = (
    # GET routes
    ("GET",  "/status",              "handlers_status",     "handle"),
    ("GET",  "/health",              "handlers_health",     "handle"),
    ("GET",  "/release/check",       "handlers_release",    "handle_check"),
    ("GET",  "/release/status",      "handlers_release",    "handle_status"),
    ("GET",  "/session",             "handlers_session",    "handle"),
    ("GET",  "/workspace/status",    "handlers_workspace",  "handle"),
    ("GET",  "/workspace/list",      "handlers_workspace",  "handle_list"),
    ("GET",  "/workspace/browse",    "handlers_workspace",  "handle_browse"),
    ("GET",  "/workspaces",          "handlers_workspace",  "handle_list"),
    ("GET",  "/project/status",      "handlers_project",    "handle_project_status"),
    ("GET",  "/project/analyze",     "handlers_project",    "handle_project_analyze"),
    ("POST", "/project/inspect",     "handlers_project",    "handle_project_inspect"),
    ("GET",  "/history",             "handlers_history",    "handle"),
    ("GET",  "/providers",           "handlers_providers",  "handle"),
    ("GET",  "/providers/cli-detect","handlers_providers",  "handle_cli_detect"),
    ("GET",  "/providers/contracts", "handlers_providers",  "handle_contracts"),
    ("GET",  "/api/v1/ui/bootstrap", "handlers_ui_bootstrap", "handle"),
    ("GET",  "/api/v1/capabilities", "handlers_capabilities", "handle_list"),
    ("GET",  "/api/v1/capability-packages", "handlers_capability_packages", "handle_list"),
    ("GET",  "/api/v1/capability-packages/receipts", "handlers_capability_packages", "handle_receipts"),
    ("GET",  "/api/v1/capability-packages/examples", "handlers_capability_packages", "handle_examples"),
    ("GET",  "/audit/project",       "handlers_audit",      "handle_project"),
    ("GET",  "/audit/bago",          "handlers_audit",      "handle_bago"),
    ("GET",  "/audit/ledger",        "handlers_audit",      "handle_ledger"),
    ("GET",  "/memory/list",         "handlers_memory",     "handle"),
    ("GET",  "/memory/status",       "handlers_memory",     "handle_status"),
    ("GET",  "/schedule/list",       "handlers_schedule",   "handle"),
    ("GET",  "/subagents/catalogue", "handlers_subagents",  "handle"),
    ("GET",  "/menu",                "handlers_menu",       "handle"),
    ("GET",  "/sources",             "handlers_files",      "handle_sources"),
    ("GET",  "/catalog/status",      "handlers_catalog",    "handle_status"),
    ("GET",  "/simulation/status",   "handlers_simulation", "handle_status"),
    ("GET",  "/simulation/events",   "handlers_simulation", "handle_events"),
    ("GET",  "/rl/status",           "handlers_rl",         "handle_status"),
    ("GET",  "/files/list",          "handlers_files",      "handle_list"),
    ("GET",  "/evidence/latest",     "handlers_evidence",   "handle_latest"),
    ("GET",  "/evidence/claims",     "handlers_evidence",   "handle_claims"),
    ("GET",  "/evidence/receipts",   "handlers_evidence",   "handle_receipts"),
    ("GET",  "/jobs/list",           "handlers_jobs",       "handle_list"),
    ("GET",  "/jobs/summary",        "handlers_jobs",       "handle_summary"),
    ("GET",  "/providers/buffer/status",  "handlers_providers",  "handle_buffer_status"),
    ("GET",  "/providers/buffer",          "handlers_providers",  "handle_buffer_status"),
    ("GET",  "/providers/blacklist",       "handlers_providers",  "handle_blacklist_get"),
    ("POST", "/providers/blacklist",       "handlers_providers",  "handle_blacklist_modify"),
    ("GET",  "/configure/auto/status",     "handlers_auto_config", "handle_auto_status"),
    ("POST", "/configure/auto/start",      "handlers_auto_config", "handle_auto_start"),
    ("POST", "/configure/auto/apply",      "handlers_auto_config", "handle_auto_apply"),
    ("POST", "/configure/auto/cancel",     "handlers_auto_config", "handle_auto_cancel"),
    ("GET",  "/plans",               "handlers_jobs",       "handle_plans_list"),
    ("GET",  "/router/list",         "handlers_router",     "handle"),
    ("GET",  "/router/policy",       "handlers_router",     "handle_policy"),
    ("GET",  "/router/session-model","handlers_router",     "handle_session_model_get"),
    ("GET",  "/router/reasoning-depth","handlers_router", "handle_reasoning_depth_get"),
    ("GET",  "/github/status",       "handlers_github",  "handle_status"),
    ("GET",  "/github/contents",     "handlers_github",  "handle_contents"),
    ("GET",  "/interpret/history",   "handlers_interpret",  "handle_history"),
    ("GET",  "/interpret/rules",     "handlers_interpret",  "handle_rules"),
    ("GET",  "/routes",              "handlers_routes",     "handle"),
    ("GET",  "/api/v1/events",       "handlers_events",     "handle"),
    # POST routes
    ("POST", "/chat",                "handlers_chat",       "handle"),
    ("POST", "/chat/stream",         "handlers_chat_stream", "handle"),
    ("POST", "/api/v1/commands",     "handlers_command",    "handle"),
    ("POST", "/api/v1/capability-packages/import", "handlers_capability_packages", "handle_import"),
    ("POST", "/api/v1/capability-packages/inspect", "handlers_capability_packages", "handle_inspect"),
    ("POST", "/command",             "handlers_command",    "handle"),
    ("POST", "/project/init",        "handlers_project",    "handle_project_init"),
    ("POST", "/project/link",        "handlers_project",    "handle_project_link"),
    ("POST", "/project/seed",        "handlers_project",    "handle_project_seed"),
    ("POST", "/project/sync",        "handlers_project",    "handle_project_sync"),
    ("POST", "/project/demo",        "handlers_project",    "handle_project_demo"),
    ("POST", "/workspace/init",      "handlers_project",    "handle_workspace_init"),
    ("POST", "/workspace/link",      "handlers_project",    "handle_workspace_link"),
    ("POST", "/workspace/seed",      "handlers_project",    "handle_workspace_seed"),
    ("POST", "/workspace/sync",      "handlers_project",    "handle_workspace_sync"),
    ("POST", "/workspace/persist",   "handlers_workspace",  "handle_persist"),
    ("POST", "/switch",              "handlers_switch",     "handle"),
    ("POST", "/catalog/config",      "handlers_catalog",    "handle_config"),
    ("POST", "/simulation/config",   "handlers_simulation", "handle_config"),
    ("POST", "/rl/shadow",           "handlers_rl",         "handle_shadow"),
    ("POST", "/rl/train-bc",         "handlers_rl",         "handle_train_bc"),
    ("POST", "/rl/eval",             "handlers_rl",         "handle_eval"),
    ("POST", "/memory/search",       "handlers_memory",     "handle_search"),
    ("POST", "/memory/embeddings/upsert", "handlers_memory", "handle_embedding_upsert"),
    ("POST", "/router/auto",         "handlers_router",     "handle_auto"),
    ("POST", "/router/session-model","handlers_router",     "handle_session_model"),
    ("POST", "/router/reasoning-depth","handlers_router", "handle_reasoning_depth"),
    ("POST", "/github/connect",      "handlers_github",  "handle_connect"),
    ("POST", "/github/create",       "handlers_github",  "handle_create"),
    ("POST", "/github/mcp-create",   "handlers_github",  "handle_mcp_create"),
    ("POST", "/workspace/conversation", "handlers_workspace_conversation", "handle"),
    ("POST", "/providers/configure", "handlers_providers",  "handle_configure"),
    ("POST", "/release/update",      "handlers_release",    "handle_update"),
    ("POST", "/release/apply",       "handlers_release",    "handle_apply"),
    ("POST", "/providers/test",      "handlers_providers",  "handle_test"),
    ("POST", "/providers/buffer/unload", "handlers_providers",  "handle_buffer_unload"),
    ("POST", "/providers/buffer/prepare", "handlers_providers", "handle_buffer_prepare"),
    ("POST", "/sources",             "handlers_files",      "handle_sources"),
    ("POST", "/files/write",         "handlers_files",      "handle_write"),
    ("POST", "/interpret",           "handlers_interpret",  "handle_post"),
    ("POST", "/vision",              "handlers_vision",     "handle"),
    ("POST", "/conversations",          "handlers_conversations", "handle_post"),
    ("GET",  "/conversations",           "handlers_conversations", "handle_get"),
    ("POST", "/plans",               "handlers_jobs",       "handle_plans_create"),
    ("POST", "/schedule",            "handlers_schedule",   "handle_create"),
)


# Single source of truth for dynamic route discovery/documentation.
# (method, path_pattern, handler_module, handler_fn)
DYNAMIC_ROUTE_META: tuple = (
    ("GET",  "/models/<provider>",                    "handlers_models",    "handle"),
    ("GET",  "/providers/<provider>/models",         "handlers_providers", "handle_list_models"),
    ("GET",  "/providers/<provider>/active-models",  "handlers_providers", "handle_active_models_get"),
    ("POST", "/providers/<provider>/active-models",  "handlers_providers", "handle_active_models_set"),
    ("GET",  "/files/read/<path:filepath>",          "handlers_files",     "handle_read"),
    ("GET",  "/evidence/receipts/<receipt_id>",      "handlers_evidence",  "handle_receipt"),
    ("GET",  "/evidence/claims/<claim_id>",          "handlers_evidence",  "handle_claim"),
    ("GET",  "/jobs/<execution_id>",                 "handlers_jobs",      "handle_get"),
    ("POST", "/jobs/<execution_id>/cancel",          "handlers_jobs",      "handle_cancel"),
    ("POST", "/jobs/<execution_id>/retry",           "handlers_jobs",      "handle_retry"),
    ("GET",  "/plans/<plan_id>",                     "handlers_jobs",      "handle_plans_get"),
    ("GET",  "/api/v1/capabilities/<capability_id>", "handlers_capabilities", "handle_get"),
    ("GET",  "/api/v1/capability-packages/<capability_id>", "handlers_capability_packages", "handle_get"),
    ("GET",  "/api/v1/capability-packages/<capability_id>/export", "handlers_capability_packages", "handle_export"),
    ("POST", "/api/v1/capability-packages/<capability_id>/enable", "handlers_capability_packages", "handle_enable"),
    ("POST", "/api/v1/capability-packages/<capability_id>/configure", "handlers_capability_packages", "handle_configure"),
    ("POST", "/api/v1/capability-packages/<capability_id>/execute", "handlers_capability_packages", "handle_execute"),
    ("POST", "/api/v1/capability-packages/<capability_id>/install-example", "handlers_capability_packages", "handle_install_example"),
    ("POST", "/plans/<plan_id>/execute",             "handlers_jobs",      "handle_plans_execute"),
    ("GET",  "/schedule/<schedule_id>",               "handlers_schedule",  "handle_get"),
    ("POST", "/schedule/<schedule_id>",               "handlers_schedule",  "handle_update"),
    ("POST", "/schedule/<schedule_id>/run",           "handlers_schedule",  "handle_run"),
    ("POST", "/schedule/<schedule_id>/delete",        "handlers_schedule",  "handle_delete"),
    ("POST", "/router/toggle/<key>",                 "handlers_router",    "handle_toggle"),
)


def _build_static_routes() -> tuple[dict, dict]:
    """Derive GET_ROUTES / POST_ROUTES from ROUTE_META so the dispatch
    table cannot diverge from the public metadata. Returns a (get_routes, post_routes)
    tuple, keeping GET and POST separate so the same path can have both verbs.
    """
    get_out: dict = {}
    post_out: dict = {}
    for method, path, mod_name, fn_name in ROUTE_META:
        if method == "GET":
            get_out[path] = _call(mod_name, fn_name)
        elif method == "POST":
            post_out[path] = _post(mod_name, fn_name)
    return get_out, post_out


_GET_ROUTES_BUILT, _POST_ROUTES_BUILT = _build_static_routes()

GET_ROUTES: dict = _GET_ROUTES_BUILT
POST_ROUTES: dict = _POST_ROUTES_BUILT


def resolve_get(handler, path: str) -> Tuple[bool, Callable | None]:
    """Return (matched, call) for a GET path. matched=False means 404."""
    if path in GET_ROUTES:
        return True, GET_ROUTES[path]
    if path.startswith("/models/"):
        provider = path[len("/models/"):]
        if provider:
            return True, _call("handlers_models", "handle", provider)
    if path.startswith("/providers/") and path.endswith("/models"):
        provider = path[len("/providers/"):-len("/models")]
        if provider and "/" not in provider:
            return True, _call("handlers_providers", "handle_list_models", provider)
    if path.startswith("/providers/") and path.endswith("/active-models"):
        provider = path[len("/providers/"):-len("/active-models")]
        if provider and "/" not in provider:
            return True, _call("handlers_providers", "handle_active_models_get", provider)
    if path.startswith("/files/read/"):
        file_path = path[len("/files/read/"):]
        return True, _call("handlers_files", "handle_read", file_path)
    if path.startswith("/evidence/receipts/"):
        receipt_id = path[len("/evidence/receipts/"):]
        return True, _call("handlers_evidence", "handle_receipt", receipt_id)
    if path.startswith("/evidence/claims/"):
        claim_id = path[len("/evidence/claims/"):]
        return True, _call("handlers_evidence", "handle_claim", claim_id)
    if path.startswith("/jobs/"):
        execution_id = path[len("/jobs/"):]
        if execution_id and execution_id != "list":
            return True, _call("handlers_jobs", "handle_get", execution_id)
    if path.startswith("/plans/") and not path.endswith("/execute"):
        plan_id = path[len("/plans/"):].strip("/")
        if plan_id and "/" not in plan_id:
            return True, _call("handlers_jobs", "handle_plans_get", plan_id)
    if path.startswith("/schedule/"):
        schedule_id = path[len("/schedule/"):].strip("/")
        if schedule_id and "/" not in schedule_id:
            return True, _call("handlers_schedule", "handle_get", schedule_id)
    if path.startswith("/api/v1/capabilities/"):
        capability_id = path[len("/api/v1/capabilities/"):].strip("/")
        if capability_id and "/" not in capability_id:
            return True, _call("handlers_capabilities", "handle_get", capability_id)
    package_prefix = "/api/v1/capability-packages/"
    if path.startswith(package_prefix):
        suffix = path[len(package_prefix):].strip("/")
        if suffix.endswith("/export"):
            package_id = suffix[:-len("/export")].strip("/")
            if package_id and "/" not in package_id:
                return True, _call("handlers_capability_packages", "handle_export", package_id)
        if suffix and "/" not in suffix:
            return True, _call("handlers_capability_packages", "handle_get", suffix)
    return False, None


def resolve_post(handler, path: str, body: dict) -> Tuple[bool, Callable | None]:
    if path in POST_ROUTES:
        return True, POST_ROUTES[path]
    if path.startswith("/jobs/") and path.endswith("/cancel"):
        execution_id = path[len("/jobs/"):-len("/cancel")].strip("/")
        if execution_id:
            return True, _call("handlers_jobs", "handle_cancel", execution_id)
    if path.startswith("/jobs/") and path.endswith("/retry"):
        execution_id = path[len("/jobs/"):-len("/retry")].strip("/")
        if execution_id:
            return True, _call("handlers_jobs", "handle_retry", execution_id)
    if path.startswith("/providers/") and path.endswith("/active-models"):
        provider = path[len("/providers/"):-len("/active-models")].strip("/")
        if provider and "/" not in provider:
            def _active_set_closure(handler, body, _p=provider):
                from handlers_providers import handle_active_models_set
                return handle_active_models_set(handler, _p, body)
            return True, _active_set_closure
    if path.startswith("/plans/") and path.endswith("/execute"):
        plan_id = path[len("/plans/"):-len("/execute")].strip("/")
        if plan_id and "/" not in plan_id:
            def _execute_closure(handler, body, _p=plan_id):
                from handlers_jobs import handle_plans_execute
                return handle_plans_execute(handler, _p, body)
            return True, _execute_closure
    if path.startswith("/schedule/"):
        suffix = path[len("/schedule/"):].strip("/")
        for action, function in (("run", "handle_run"), ("delete", "handle_delete")):
            ending = f"/{action}"
            if suffix.endswith(ending):
                schedule_id = suffix[:-len(ending)].strip("/")
                if schedule_id and "/" not in schedule_id:
                    def _schedule_action(handler, body, _id=schedule_id, _fn=function):
                        module = importlib.import_module("handlers_schedule")
                        return getattr(module, _fn)(handler, _id)
                    return True, _schedule_action
        if suffix and "/" not in suffix:
            def _schedule_update(handler, body, _id=suffix):
                from handlers_schedule import handle_update
                return handle_update(handler, _id, body)
            return True, _schedule_update
    package_prefix = "/api/v1/capability-packages/"
    if path.startswith(package_prefix):
        suffix = path[len(package_prefix):].strip("/")
        for action, function in (
            ("enable", "handle_enable"),
            ("configure", "handle_configure"),
            ("execute", "handle_execute"),
            ("install-example", "handle_install_example"),
        ):
            ending = f"/{action}"
            if suffix.endswith(ending):
                package_id = suffix[:-len(ending)].strip("/")
                if package_id and "/" not in package_id:
                    return True, _call("handlers_capability_packages", function, package_id)
    return False, None


def resolve_router(handler, path: str, body: dict) -> Tuple[bool, Callable | None]:
    """Pattern route: POST /router/toggle/<provider>/<model>.

    The key is in the URL, not the body, so we wrap the handler to
    ignore the body argument that do_POST passes in.
    """
    if path.startswith("/router/toggle/"):
        key = path[len("/router/toggle/"):]
        if key:
            mod = importlib.import_module("handlers_router")
            def _toggler(handler, body, _key=key):
                return mod.handle_toggle(handler, _key)
            return True, _toggler
    return False, None


API_PREFIXES = (
    "/api",
    "/api/v1",
    "/status",
    "/health",
    "/session",
    "/workspace",
    "/workspaces",
    "/project",
    "/history",
    "/conversations",
    "/providers",
    "/menu",
    "/sources",
    "/models",
    "/chat",
    "/chat/stream",
    "/command",
    "/switch",
    "/catalog",
    "/audit",
    "/simulation",
    "/rl",
    "/files",
    "/evidence",
    "/memory",
    "/jobs",
    "/schedule",
    "/subagents",
    "/router",
    "/interpret",
    "/routes",
    "/api/v1/events",
    "/vision",
    "/plans",
    "/configure",
    "/release",
    "/github",
)
