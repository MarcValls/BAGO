"""Load and normalize the BAGO agent pack from an external catalog."""

from __future__ import annotations

import re
import os
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

from bago_core.agent_kit.errors import AgentDefinitionError, AgentNotFound, CatalogNotFound
from bago_core.agent_kit.models import AgentDefinition


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bundled_catalog_candidates() -> tuple[Path, ...]:
    repo_root = _repository_root()
    return (
        repo_root / ".github" / "agents",
        repo_root / ".codex" / "agents",
    )


def _catalog_roots(catalog: Path) -> tuple[Path, ...]:
    repo_root = _repository_root().resolve()
    if catalog.resolve() == repo_root:
        roots = tuple(candidate for candidate in _bundled_catalog_candidates() if candidate.is_dir())
        if roots:
            return roots
    return (catalog,)


def default_catalog_path() -> Path:
    """Resolve the live default catalog, preferring tracked repo agents."""
    configured = os.environ.get("BAGO_AGENT_CATALOG", "").strip()
    if configured:
        return Path(configured).expanduser()
    if any(candidate.is_dir() for candidate in _bundled_catalog_candidates()):
        return _repository_root()
    return Path.home() / "BAGO_AGENTIC_DATA_LAB" / "agents"


DEFAULT_CATALOG_PATH = default_catalog_path()

# Priority order for definition sources per agent id.
_SOURCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("toml", r"{id_underscore}.toml"),
    ("agent_md", r"{id_dash}.agent.md"),
    ("agent_json", r"{id_underscore}.agent.json"),
)


def _id_underscore(agent_id: str) -> str:
    return agent_id.replace("-", "_")


def _id_dash(agent_id: str) -> str:
    return agent_id.replace("_", "-")


def _canonical_id(raw_id: str) -> str:
    """Normalize id to underscores, lowercase, alphanumerics."""
    cid = str(raw_id).strip().lower().replace(" ", "_").replace(".", "_").replace("-", "_")
    if not re.match(r"^[a-z0-9_]+$", cid):
        raise AgentDefinitionError(f"invalid agent id {raw_id!r}")
    return cid


def _find_definition_file(catalog: Path, agent_id: str) -> tuple[str, Path] | None:
    for kind, pattern in _SOURCE_PATTERNS:
        candidate_name = pattern.format(
            id_underscore=_id_underscore(agent_id),
            id_dash=_id_dash(agent_id),
        )
        for root in _catalog_roots(catalog):
            for found in root.rglob(candidate_name):
                if found.is_file():
                    return kind, found
    return None


def _parse_toml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return tomllib.loads(text)


def _parse_agent_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise AgentDefinitionError(f"agent JSON must contain an object: {path}")
    return raw


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    try:
        _, front, body = text.split("---", 2)
    except ValueError:
        return {}
    data: dict[str, Any] = {}
    if yaml is not None:
        try:
            data = yaml.safe_load(front) or {}
        except Exception:
            pass
    if not data:
        try:
            data = tomllib.loads(front)
        except Exception:
            pass
    data["_body"] = body.strip()
    return data


def _infer_category(definition: dict[str, Any], description: str) -> str:
    category = str(definition.get("category", "")).strip().lower()
    if category:
        return category
    desc = description.lower()
    if re.search(r"\b(verificador|verifier)\b", desc):
        return "verify"
    if definition.get("sandbox_mode") == "read-only" or any(word in desc for word in ("auditor", "audit")):
        return "audit"
    if any(word in desc for word in ("orquest", "gabinete", "coordin", "assistant")):
        return "orchestrate"
    if any(word in desc for word in ("implement", "worker", "engineer")):
        return "implement"
    return "unknown"


def _normalize(definition: dict[str, Any], path: Path, kind: str) -> AgentDefinition:
    raw_id = definition.get("name") or definition.get("id") or definition.get("agent")
    if not raw_id:
        raise AgentDefinitionError(f"missing name/id in {path}")

    agent_id = _canonical_id(raw_id)

    description = definition.get("description", "") or definition.get("mission", "")
    if isinstance(description, list):
        description = " ".join(description)
    description = str(description).strip()

    metadata = dict(definition)
    metadata.pop("_body", None)
    metadata.setdefault("source_kind", kind)

    if kind == "agent_json" and "sandbox_mode" not in metadata:
        metadata["sandbox_mode"] = "workspace-write" if metadata.get("writes") else "read-only"

    category = _infer_category(metadata, description)

    prompt = definition.get("_body") or definition.get("developer_instructions") or definition.get("instructions", "")
    if not prompt and kind == "agent_json":
        fields = ("role", "mission", "reads", "writes", "tools", "gate", "on_failure", "loop", "sense", "plan", "act", "observe", "learn")
        prompt = "\n".join(
            f"{field}: {json.dumps(definition[field], ensure_ascii=False)}"
            for field in fields if field in definition
        )
    if isinstance(prompt, list):
        prompt = "\n".join(str(item) for item in prompt)

    return AgentDefinition(
        id=agent_id,
        name=str(definition.get("name", agent_id)).strip(),
        description=description,
        category=category,
        sandbox_mode=str(metadata.get("sandbox_mode", "read-only")).strip().lower(),
        model=str(metadata.get("model", "")).strip(),
        model_reasoning_effort=str(metadata.get("model_reasoning_effort", "")).strip(),
        prompt_template=str(prompt).strip(),
        source_path=path,
        metadata=metadata,
    )


def load_agent(catalog_path: Path | str, agent_id: str) -> AgentDefinition:
    catalog = Path(catalog_path).expanduser().resolve()
    if not catalog.exists():
        raise CatalogNotFound(f"catalog not found: {catalog}")

    found = _find_definition_file(catalog, agent_id)
    if found is None:
        raise AgentNotFound(f"agent {agent_id!r} not found in {catalog}")

    kind, path = found
    if kind == "toml":
        raw = _parse_toml(path)
    elif kind == "agent_json":
        raw = _parse_agent_json(path)
    else:
        raw = _parse_frontmatter(path)

    return _normalize(raw, path, kind)


def list_agents(catalog_path: Path | str | None = None) -> list[AgentDefinition]:
    catalog = Path(catalog_path or DEFAULT_CATALOG_PATH).expanduser().resolve()
    if not catalog.exists():
        raise CatalogNotFound(f"catalog not found: {catalog}")

    agents: list[AgentDefinition] = []
    seen: set[str] = set()

    for kind, glob in (("toml", "*.toml"), ("agent_md", "*.agent.md"), ("agent_json", "*.agent.json")):
        for root in _catalog_roots(catalog):
            for path in root.rglob(glob):
                if not path.is_file():
                    continue
                try:
                    if kind == "toml":
                        raw = _parse_toml(path)
                    elif kind == "agent_json":
                        raw = _parse_agent_json(path)
                    else:
                        raw = _parse_frontmatter(path)
                    agent = _normalize(raw, path, kind)
                except AgentDefinitionError:
                    continue
                if agent.id in seen:
                    continue
                seen.add(agent.id)
                agents.append(agent)

    return sorted(agents, key=lambda a: a.id)
