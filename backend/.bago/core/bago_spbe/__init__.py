"""BAGO Semantic Procedural Behavior Engine (SPBE).

Contract-bound semantic decision engine. It proposes or terminates semantically;
it never issues authorization and never executes material effects.
"""
from .engine import SemanticProceduralBehaviorEngine
from .pipeline import SPBEPipeline
from .ports import (
    CapabilityDiscoveryPort,
    IdentityNormalizer,
    NoopResourceBinder,
    ResourceBindingPort,
    SemanticInterpreterPort,
    SemanticNormalizerPort,
    StaticCapabilityDiscovery,
)
from .model import *

__all__ = [
    "SemanticProceduralBehaviorEngine",
    "SPBEPipeline",
    "SemanticInterpreterPort",
    "SemanticNormalizerPort",
    "CapabilityDiscoveryPort",
    "ResourceBindingPort",
    "IdentityNormalizer",
    "StaticCapabilityDiscovery",
    "NoopResourceBinder",
]
__version__ = "0.1.0"
