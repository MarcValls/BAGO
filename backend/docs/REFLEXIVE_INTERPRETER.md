# Reflexive Interpreter Contract

Status: implementation_started
Owner: BAGO core

## Purpose

This contract defines the active reflexive interpretation surface for the current system.
It keeps the interpretation pipeline auditable and aligned with the current shell.

## CAPTAR Complement

The Complemento operativo CAPTAR is accepted as an operational complement to the reflexive interpreter.
It does not replace `ReflexiveQuestionRecord`, `ContextEnvelope` or `ContextReceipt`.
It defines the pre-response sequence used to turn a question into a response contract.

Reference: `docs/CAPTAR_INTERPRETATION_MAPPING.md`.

## Scope

- Read a question and its context.
- Separate literal reading, intent, unknowns, and constraints.
- Detect ambiguity and self-reference.
- Produce a formalization with evidence and limits.
- Persist audit material for the current tree.

## Validation

- `tests/test_reflexive_interpreter.py`
- `tests/test_task_response_contract.py`
- `tests/test_context_receipt_validator.py`
