"""npath — Neural Path System.

Un sistema local de grafos versionados donde las ramas funcionan como
trayectorias cognitivas activables, fusionables y reversibles.

Uso rápido:
    python -m npath --help
    bago npath status
"""
from npath._db import DB_PATH, STATE_DIR, cmd_init
from npath._graph import (
    cmd_branch, cmd_branches, cmd_commit,
    cmd_merge, cmd_unmerge, cmd_reactivate_merge,
    cmd_split, cmd_activate, cmd_deactivate,
)
from npath._view import cmd_log, cmd_map, cmd_status, cmd_node, cmd_delete_node, cmd_recall
from npath._ollama import cmd_think, cmd_reflect, cmd_suggest, cmd_evolve, cmd_ollama_status
from npath._embeddings import cmd_embed, cmd_similar

__all__ = [
    "DB_PATH", "STATE_DIR",
    "cmd_init",
    "cmd_branch", "cmd_branches", "cmd_commit",
    "cmd_merge", "cmd_unmerge", "cmd_reactivate_merge",
    "cmd_split", "cmd_activate", "cmd_deactivate",
    "cmd_log", "cmd_map", "cmd_status", "cmd_node", "cmd_delete_node", "cmd_recall",
    "cmd_think", "cmd_reflect", "cmd_suggest", "cmd_evolve", "cmd_ollama_status",
    "cmd_embed", "cmd_similar",
]
