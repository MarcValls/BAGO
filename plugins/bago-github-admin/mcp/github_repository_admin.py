#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

SERVER_NAME = "bago-github-repository-admin"
SERVER_VERSION = "0.3.0"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def token_from_environment() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(key)
        if value:
            return value.strip()
    try:
        p = subprocess.run(["gh", "auth", "token"], text=True, capture_output=True, timeout=8)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


@dataclass
class GitHubAPI:
    base_url: str
    token: str

    def call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.base_url.rstrip("/") + path
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("User-Agent", SERVER_NAME + "/" + SERVER_VERSION)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                return json.loads(data.decode("utf-8")) if data else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw)
            except json.JSONDecodeError:
                detail = {"message": raw[:1000]}
            message = detail.get("message") if isinstance(detail, dict) else str(detail)
            raise RuntimeError(f"GitHub API {method} {path} failed with HTTP {exc.code}: {message}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"GitHub API {method} {path} unavailable: {exc.reason}") from None


def require_api() -> GitHubAPI:
    token = token_from_environment()
    if not token:
        raise RuntimeError("GitHub authentication unavailable. Set GITHUB_TOKEN/GH_TOKEN or authenticate the GitHub CLI.")
    return GitHubAPI(os.environ.get("GITHUB_API_URL", "https://api.github.com"), token)


def normalize_visibility(value: str | None) -> str:
    v = (value or "private").lower()
    if v not in {"private", "public"}:
        raise ValueError("visibility must be 'private' or 'public'")
    return v


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError("name must be 1-100 characters using letters, digits, '.', '_' or '-'")
    return name


def create_repository(arguments: dict[str, Any]) -> dict[str, Any]:
    name = validate_name(arguments.get("name", ""))
    visibility = normalize_visibility(arguments.get("visibility"))
    description = arguments.get("description") or ""
    auto_init = bool(arguments.get("auto_init", False))
    owner_requested = arguments.get("owner")
    if owner_requested is not None and (not isinstance(owner_requested, str) or not owner_requested.strip()):
        raise ValueError("owner must be a non-empty string when supplied")

    api = require_api()
    viewer = api.call("GET", "/user")
    viewer_login = viewer.get("login") if isinstance(viewer, dict) else None
    if not viewer_login:
        raise RuntimeError("Could not resolve the authenticated GitHub login")
    owner = owner_requested.strip() if isinstance(owner_requested, str) else viewer_login

    payload: dict[str, Any] = {
        "name": name,
        "description": str(description),
        "private": visibility == "private",
        "auto_init": auto_init,
    }
    if owner.lower() == viewer_login.lower():
        create_path = "/user/repos"
    else:
        create_path = "/orgs/" + urllib.parse.quote(owner, safe="") + "/repos"

    created = api.call("POST", create_path, payload)
    created_owner = ((created.get("owner") or {}).get("login") if isinstance(created, dict) else None) or owner
    observed_path = "/repos/{}/{}".format(
        urllib.parse.quote(str(created_owner), safe=""), urllib.parse.quote(name, safe="")
    )
    observed = api.call("GET", observed_path)

    observed_owner = ((observed.get("owner") or {}).get("login") if isinstance(observed, dict) else None)
    observed_name = observed.get("name") if isinstance(observed, dict) else None
    observed_private = observed.get("private") if isinstance(observed, dict) else None
    observed_visibility = "private" if observed_private is True else "public" if observed_private is False else observed.get("visibility")
    identity_match = bool(
        isinstance(observed_owner, str)
        and observed_owner.lower() == str(created_owner).lower()
        and observed_name == name
        and observed_visibility == visibility
    )
    full_name = observed.get("full_name") if isinstance(observed, dict) else None
    if not full_name and observed_owner and observed_name:
        full_name = f"{observed_owner}/{observed_name}"

    return {
        "created": True,
        "verified": identity_match,
        "owner": observed_owner or created_owner,
        "name": observed_name or name,
        "full_name": full_name,
        "visibility": observed_visibility,
        "default_branch": observed.get("default_branch") if isinstance(observed, dict) else None,
        "repository_id": observed.get("id") if isinstance(observed, dict) else None,
        "html_url": observed.get("html_url") if isinstance(observed, dict) else None,
        "verification": {
            "method": "read-after-write",
            "endpoint": observed_path,
            "identity_match": identity_match,
        },
    }


INPUT_SCHEMA = {
    "type": "object",
    "required": ["name", "visibility"],
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 100, "description": "GitHub repository name."},
        "owner": {"type": "string", "minLength": 1, "description": "GitHub user or organization owner. Omit for the authenticated user."},
        "description": {"type": "string", "description": "Repository description."},
        "visibility": {"type": "string", "enum": ["private", "public"], "description": "Requested repository visibility."},
        "auto_init": {"type": "boolean", "default": False, "description": "Whether GitHub initializes the repository."},
    },
    "additionalProperties": False,
}
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["created", "verified", "owner", "name", "visibility", "verification"],
    "properties": {
        "created": {"type": "boolean"},
        "verified": {"type": "boolean"},
        "owner": {"type": "string"},
        "name": {"type": "string"},
        "full_name": {"type": ["string", "null"]},
        "visibility": {"type": ["string", "null"]},
        "default_branch": {"type": ["string", "null"]},
        "repository_id": {},
        "html_url": {"type": ["string", "null"]},
        "verification": {"type": "object"},
    },
    "additionalProperties": True,
}

TOOL = {
    "name": "create_repository",
    "title": "Create GitHub repository",
    "description": "Create one GitHub repository and verify its resulting owner/name/visibility with a read-after-write lookup.",
    "inputSchema": INPUT_SCHEMA,
    "outputSchema": OUTPUT_SCHEMA,
    "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True},
}


def tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name != "create_repository":
        raise ValueError(f"Unknown tool: {name}")
    result = create_repository(arguments)
    return {
        "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
        "structuredContent": result,
        "isError": False,
    }


def response(req_id: Any, result: Any = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    return out


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = msg.get("method")
    req_id = msg.get("id")
    if method and req_id is None:
        return None
    try:
        if method == "initialize":
            return response(req_id, {
                "protocolVersion": (msg.get("params") or {}).get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })
        if method == "ping":
            return response(req_id, {})
        if method == "tools/list":
            return response(req_id, {"tools": [TOOL]})
        if method == "tools/call":
            params = msg.get("params") or {}
            return response(req_id, tool_call(params.get("name", ""), params.get("arguments") or {}))
        return response(req_id, error={"code": -32601, "message": f"Method not found: {method}"})
    except Exception as exc:
        if method == "tools/call":
            result = {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True,
            }
            return response(req_id, result)
        return response(req_id, error={"code": -32000, "message": f"{type(exc).__name__}: {exc}"})


def stdio_loop() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            out = handle(msg)
        except Exception as exc:
            out = response(None, error={"code": -32700, "message": f"Parse error: {exc}"})
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


def self_check() -> int:
    assert TOOL["annotations"] == {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}
    assert validate_name("bago-test.repo_01") == "bago-test.repo_01"
    try:
        validate_name("bad/name")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid repository name accepted")
    init = handle({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}})
    assert init and init["result"]["serverInfo"]["name"] == SERVER_NAME
    listed = handle({"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}})
    assert listed and listed["result"]["tools"][0]["name"] == "create_repository"
    print(json.dumps({"ok": True, "server": SERVER_NAME, "version": SERVER_VERSION, "tool": TOOL["name"]}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdio", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if args.stdio:
        return stdio_loop()
    ap.error("use --stdio or --self-check")
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
