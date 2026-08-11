# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary user is a technical or semi-technical person who wants to turn an idea into an application or automation without manually configuring every model, capability, and execution step.

## Product Purpose

BAGO combines guided conversation, reusable capabilities, executable pipelines, scheduling, and evidence so users can create and operate applications or recurring tasks from one workspace. Success means moving from an idea or external package to a controlled, repeatable execution with visible state and receipts.

## Positioning

BAGO treats chat, context, capabilities, pipelines, provider routing, and execution evidence as parts of one governed workflow. The same versioned package contract is used to import and export capabilities and pipelines.

## Operating Context

Users work with local repositories, files, provider accounts, reusable templates, external capability or pipeline packages, scheduled jobs, and execution receipts. They may start from a conversation, an idea, a template, or a package created outside BAGO.

## Capabilities and Constraints

- Conversations are persistent, isolated, recoverable, renameable, and archivable.
- Pipelines may be declarative or executable and can compose capabilities and other pipelines.
- External packages use a concrete, versioned ZIP contract with schemas, file digests, compatibility metadata, dependencies, permissions, and optional signatures.
- Unsigned packages may be imported with a warning, but code execution and sensitive permissions require explicit confirmation.
- Provider token availability may influence automatic routing only when a provider exposes a reliable signal; unknown balances are displayed as unknown.
- Returning to Inicio is a navigation action and must not erase conversations or work.

## Brand Commitments

The product name is BAGO. Interface copy is direct, operational, and primarily Spanish. Technical terms such as Pipeline and Receipt remain visible when they identify durable product concepts.

## Evidence on Hand

The repository includes persistent conversation storage, a plan engine, provider routing, capability package execution with receipts, and local capability examples under `examples/capabilities/`. Product claims must be demonstrated through those contracts and receipts rather than fabricated metrics.

## Product Principles

1. Start from the user's goal, not system configuration.
2. Keep powerful controls contextual to the task where they matter.
3. Make external artifacts portable through one concrete contract.
4. Separate import and inspection from activation and execution.
5. Preserve state and show evidence for every meaningful execution.

## Accessibility & Inclusion

All primary flows must support keyboard navigation, visible focus, semantic states, understandable errors, and responsive layouts for desktop and narrow web viewports.
