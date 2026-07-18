from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

from .loader import load_module_from_path
from .snapshot import resolve_piece_path


def add_piece_paths(*piece_names: str) -> None:
    for piece_name in piece_names:
        path = resolve_piece_path(piece_name)
        path_s = str(path)
        if path_s not in sys.path:
            sys.path.insert(0, path_s)


def load_piece_module(piece_name: str, module_name: str, relative_file: str) -> ModuleType:
    path = resolve_piece_path(piece_name) / relative_file
    return load_module_from_path(module_name, Path(path))
