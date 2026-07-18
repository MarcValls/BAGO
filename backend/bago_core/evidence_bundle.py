#!/usr/bin/env python3
"""FASE 6.3: compat shim for evidence_bundle.

The original 610-line monolith has been split into three modules:

- :mod:`bago_core.evidence_model`     -- data model + ContractMockAdapter
- :mod:`bago_core.evidence_generator` -- storage / IO / generator logic
- :mod:`bago_core.evidence_cli`       -- argparse + run/main

This module re-exports the public API so legacy imports keep working:

    from bago_core.evidence_bundle import (  # legacy
        ContractMockAdapter, generate_bundle, build_parser, run, main,
        PROFILES, ObjectiveProfile, _run_tests,
    )

R0-R10: facade only. All business logic lives in the modules above.
"""
from __future__ import annotations

from bago_core.evidence_model import (
    ContractMockAdapter,
    ObjectiveProfile,
    PROFILES,
    registered_mock_adapter,
)
from bago_core.evidence_generator import (
    generate_bundle,
)
from bago_core.evidence_cli import (
    build_parser,
    main,
    run,
    _run_tests,
)

__all__ = [
    "ContractMockAdapter",
    "ObjectiveProfile",
    "PROFILES",
    "registered_mock_adapter",
    "generate_bundle",
    "build_parser",
    "main",
    "run",
    "_run_tests",
]
