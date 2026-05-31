# BAGO v4 RL Engine

BAGO v4 treats RL as an observer first. RL can recommend, score, and log. It must not execute autonomous actions by default.

## Current Local RL

Current code:

- `.bago/core/rl_engine.py`
- `.bago/api/control_shadow.py`
- E2E coverage for feedback path.

Current role:

- collect feedback.
- store rewards/preferences.
- expose simple policy primitives.
- support shadow/control simulation.

## RL Bridge

Current code:

- `bago_core/rl_bridge.py`
- `bago_core/rl_policies.py`

Current commands:

```powershell
python bago_core\cli.py rl status
python bago_core\cli.py rl shadow on
python bago_core\cli.py rl shadow status
python bago_core\cli.py rl shadow off
```

State and transitions:

```text
.bago\state\rl_bridge.json
.bago\state\rl_transitions.jsonl
```

Rule: these files are live state and must not be packaged.

## Policy Layer

Source:

```text
C:\bago_true\.bago\rl
```

Implemented:

1. LinUCB policy.
2. Behavioral Cloning.
3. `bago rl train bc`.
4. `bago rl eval`.
5. numpy fallback.

Current command behavior:

- if no transition samples exist, `train bc` reports `no_samples`.
- if no policy exists, `eval` reports `no_policy`.
- if numpy is missing, policy commands report `disabled`.
- all policy reports include `can_execute=False`.

Still future:

- train from rich real datasets.
- checkpoint import.
- canary only after evidence.

Experimental and non-blocking:

- PPO.
- QMIX.
- heavy checkpoints.
- full autonomous mode.

## Policy Commands

```powershell
python bago_core\cli.py rl train bc
python bago_core\cli.py rl eval
```

## Authority Model

| Mode | Authority | Distribution default |
|---|---|---|
| `off` | none | allowed |
| `shadow` | observe and recommend | default target |
| `canary` | limited guarded suggestions | future |
| `full` | autonomous actions | not allowed by default |

## Data Rules

Do not package:

- live RL state.
- private traces.
- checkpoints from `bago_true`.
- logs containing user content.

Allowed:

- code adapters.
- public sample data.
- generated evidence with explicit objective.
- policy interfaces without private weights.

## Failure Policy

If RL fails:

- keep core v4 running.
- keep CLI valid.
- report `rl unavailable`.
- never silently promote to canary/full.

## Next Steps

1. Add richer transition features.
2. Add optional checkpoint import with checksum and exclusion checks.
3. Add policy quality metrics before canary.
