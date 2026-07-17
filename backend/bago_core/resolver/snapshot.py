from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .aliases import build_alias_index
from .discovery import resolve_candidates
from .manifest import load_contract
from .roots import framework_root


@dataclass(frozen=True)
class ResolverEntry:
    id: str
    kind: str
    loader: str
    candidates: tuple[str, ...]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolverSnapshot:
    source_path: Path
    schema_version: int
    entries: tuple[ResolverEntry, ...]
    aliases: dict[str, str]


@dataclass(frozen=True)
class Resolution:
    piece_id: str
    path: Path
    candidate: str
    exists: bool


def load_snapshot(contract_path: str | Path | None = None) -> ResolverSnapshot:
    contract = load_contract(contract_path)
    entries = tuple(_parse_entry(item) for item in contract.get("pieces", []))
    source_path = Path(contract_path) if contract_path is not None else framework_root() / "docs" / "contracts" / "resolver_contract.json"
    return ResolverSnapshot(
        source_path=source_path,
        schema_version=int(contract.get("schema_version", 1)),
        entries=entries,
        aliases=build_alias_index(entries),
    )


def resolve_piece(piece_name: str, *, contract_path: str | Path | None = None) -> Resolution:
    snapshot = load_snapshot(contract_path)
    piece_id = snapshot.aliases.get(piece_name, piece_name)
    entry = next((item for item in snapshot.entries if item.id == piece_id), None)
    if entry is None:
        raise KeyError(f"resolver piece not found: {piece_name}")
    path, candidate = resolve_candidates(entry.candidates)
    exists = path.exists()
    return Resolution(piece_id=entry.id, path=path, candidate=candidate, exists=exists)


def resolve_piece_path(piece_name: str, *, contract_path: str | Path | None = None) -> Path:
    return resolve_piece(piece_name, contract_path=contract_path).path


def _parse_entry(item: dict[str, Any]) -> ResolverEntry:
    try:
        piece_id = str(item["id"]).strip()
        kind = str(item["kind"]).strip()
        loader = str(item.get("loader", "path")).strip()
        candidates = tuple(str(candidate).strip() for candidate in item.get("candidates", []) if str(candidate).strip())
        aliases = tuple(str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip())
    except Exception as exc:  # pragma: no cover - defensive parsing
        raise ValueError(f"invalid resolver entry: {item!r}") from exc
    if not piece_id or not kind or not candidates:
        raise ValueError(f"resolver entry missing required fields: {item!r}")
    return ResolverEntry(id=piece_id, kind=kind, loader=loader, candidates=candidates, aliases=aliases)
