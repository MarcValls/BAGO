"""Tests del validador de scope."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from integrations.pi.errors import (
    ScopeLinkEscapeDenied,
    ScopePathDenied,
    ScopeToctouDetected,
)
from integrations.pi.scope_validator import (
    assert_within_scope,
    deny_implicit_pi_sources,
    find_violations,
    resolve_path,
    verify_toctou,
)


def test_resolve_path_inside(tmp_path: Path) -> None:
    inside = tmp_path / "src" / "file.py"
    inside.parent.mkdir(parents=True)
    inside.write_text("x", encoding="utf-8")
    resolved = resolve_path(str(inside), str(tmp_path))
    assert resolved.inside_scope
    assert resolved.exists


def test_resolve_path_outside(tmp_path: Path) -> None:
    # Usamos un directorio claramente fuera de scope (raíz del sistema
    # en Unix, o C:\ en Windows). El archivo puede o no existir; lo
    # que importa es que el path resuelto no caiga bajo tmp_path.
    outside = Path("C:/" if os.name == "nt" else "/")
    target = outside / "bago-pi-evil-test-12345.txt"
    # assert_within_scope es el gate que rechaza; resolve_path sólo
    # reporta la posición.
    with pytest.raises(ScopePathDenied):
        assert_within_scope(str(target), str(tmp_path))


def test_assert_within_scope_rejects_traversal(tmp_path: Path) -> None:
    target = tmp_path / "ok.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(ScopePathDenied):
        assert_within_scope(str(tmp_path / ".." / "evil.txt"), str(tmp_path))


def test_symlink_inside_scope_is_allowed(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("hi", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    resolved = assert_within_scope(str(link), str(tmp_path))
    assert resolved.inside_scope


def test_symlink_escape_denied(tmp_path: Path) -> None:
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    target = outside_dir / "secret.txt"
    target.write_text("top secret", encoding="utf-8")
    link = tmp_path / "escape"
    try:
        os.symlink(str(target), str(link))
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises((ScopeLinkEscapeDenied, ScopePathDenied)):
        assert_within_scope(str(link), str(tmp_path))


def test_toctou_detection(tmp_path: Path) -> None:
    target = tmp_path / "ok.txt"
    target.write_text("x", encoding="utf-8")
    resolved = resolve_path(str(target), str(tmp_path))
    stat = os.stat(resolved.canonical)
    target.unlink()
    target.write_text("y", encoding="utf-8")
    with pytest.raises(ScopeToctouDetected):
        verify_toctou(resolved, stat)


def test_find_violations(tmp_path: Path) -> None:
    inside = tmp_path / "ok.txt"
    inside.write_text("x", encoding="utf-8")
    outside = tmp_path.parent / "evil.txt"
    outside.write_text("x", encoding="utf-8")
    bad = find_violations(str(tmp_path), [str(inside), str(outside)])
    assert str(outside) in bad
    assert str(inside) not in bad


def test_deny_implicit_pi_sources(tmp_path: Path) -> None:
    (tmp_path / ".pi").mkdir()
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    found = deny_implicit_pi_sources(str(tmp_path))
    assert any(p.endswith(".pi") for p in found)


def test_unc_on_non_windows_rejected() -> None:
    if os.name == "nt":
        pytest.skip("windows only behaviour")
    with pytest.raises(ScopePathDenied):
        resolve_path(r"\\server\share\file", str("/tmp"))
