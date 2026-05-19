
from .agents import _cmd_agents
from .auth import _cmd_auth, _cmd_login
from .auto import _cmd_auto
from .catalog import cmd_catalog
from .config import _cmd_config
from .framework import _cmd_framework
from .generative import _cmd_generative
from .main_menu import _cmd_main_menu
from .memory import _cmd_memory
from .projects import _cmd_projects
from .roles import _cmd_roles
from .routing import _cmd_routing
from .scan import _cmd_scan
from .session_menu import _cmd_session
from .skills import _cmd_skills
from .sync import _cmd_sync
from .wizard import _cmd_wizard
from .workspaces import _cmd_workspaces

__all__ = [
    "_cmd_agents",
    "_cmd_auth",
    "_cmd_login",
    "_cmd_auto",
    "cmd_catalog",
    "_cmd_config",
    "_cmd_framework",
    "_cmd_generative",
    "_cmd_main_menu",
    "_cmd_memory",
    "_cmd_projects",
    "_cmd_roles",
    "_cmd_routing",
    "_cmd_scan",
    "_cmd_session",
    "_cmd_skills",
    "_cmd_sync",
    "_cmd_wizard",
    "_cmd_workspaces",
]
