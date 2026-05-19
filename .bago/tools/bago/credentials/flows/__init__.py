"""bago.credentials.flows — Re-exporta todos los flujos de login."""

from .github import flow_github
from .openai import flow_openai
from .ollama import flow_ollama_cloud, flow_ollama_service, flow_opencode
from .git import flow_gittoken
from .misc import flow_api_key, flow_huggingface, flow_sendcm

__all__ = [
    "flow_github",
    "flow_openai",
    "flow_ollama_cloud",
    "flow_ollama_service",
    "flow_opencode",
    "flow_gittoken",
    "flow_api_key",
    "flow_huggingface",
    "flow_sendcm",
]
