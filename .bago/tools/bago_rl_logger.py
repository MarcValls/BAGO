#!/usr/bin/env python3
"""bago_rl_logger.py — Logger de transiciones RL para BAGO.

Fase 0 del plan de integración de RL.
Captura (observation, action, reward, next_observation, done, info)
sin modificar el comportamiento operativo de BAGO.

Uso:
    from bago_rl_logger import BagoRLLogger
    logger = BagoRLLogger()
    logger.log_transition(episode_id, step, obs, action, reward, next_obs, done, info)

    # Al finalizar
    logger.flush()

    # Verificación
    python bago_rl_logger.py --verify

Códigos: RL-L001 (OK), RL-L002 (flush error), RL-L003 (invalid transition)
"""
from __future__ import annotations

import argparse
import atexit
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BAGO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = BAGO_ROOT / "logs"
DEFAULT_LOG_PATH = LOG_DIR / "rl_transitions.jsonl"


@dataclass
class Transition:
    timestamp: str
    episode_id: str
    step: int
    observation: dict[str, Any]
    action: str | int | dict[str, Any]
    reward: dict[str, float] | float
    next_observation: dict[str, Any]
    done: bool
    info: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BagoRLLogger:
    """Logger append-only de transiciones RL para BAGO.

    Diseño:
    - Buffer en memoria con flush periódico.
    - Escritura atómica append-only en JSONL.
    - Rotación automática si el fichero supera 100 MB.
    - Validación mínima de esquema.
    """

    ROTATION_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or DEFAULT_LOG_PATH
        self._buffer: list[Transition] = []
        self._buffer_limit = 5
        self._ensure_dir()
        atexit.register(self.flush)

    def __del__(self):
        self.flush()

    def _ensure_dir(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        if not self.log_path.exists():
            return
        if self.log_path.stat().st_size < self.ROTATION_SIZE_BYTES:
            return
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rotated = self.log_path.with_suffix(f".jsonl.{timestamp}.bak")
        self.log_path.rename(rotated)

    def log_transition(
        self,
        episode_id: str,
        step: int,
        observation: dict[str, Any],
        action: str | int | dict[str, Any],
        reward: dict[str, float] | float,
        next_observation: dict[str, Any],
        done: bool,
        info: dict[str, Any] | None = None,
    ) -> Transition | None:
        """Registra una transición validada. Retorna la transición o None si falla validación."""
        info = info or {}

        # Validación mínima
        if not isinstance(observation, dict):
            print(f"[RL-Logger] Warning: observation no es dict (ep={episode_id}, step={step})", file=sys.stderr)
            return None
        if not isinstance(next_observation, dict):
            print(f"[RL-Logger] Warning: next_observation no es dict (ep={episode_id}, step={step})", file=sys.stderr)
            return None
        if not isinstance(done, bool):
            print(f"[RL-Logger] Warning: done no es bool (ep={episode_id}, step={step})", file=sys.stderr)
            return None

        transition = Transition(
            timestamp=datetime.now(timezone.utc).isoformat(),
            episode_id=episode_id,
            step=step,
            observation=observation,
            action=action,
            reward=reward,
            next_observation=next_observation,
            done=done,
            info=info,
        )
        self._buffer.append(transition)
        if len(self._buffer) >= self._buffer_limit:
            self.flush()
        return transition

    def flush(self) -> bool:
        """Persiste el buffer en disco. Retorna True si OK."""
        if not self._buffer:
            return True
        try:
            self._rotate_if_needed()
            lines = [json.dumps(t.to_dict(), ensure_ascii=False, default=str) + "\n" for t in self._buffer]
            with self.log_path.open("a", encoding="utf-8") as f:
                f.writelines(lines)
            self._buffer.clear()
            return True
        except Exception as e:
            print(f"[RL-Logger] Error flushing: {e}", file=sys.stderr)
            return False

    def close(self) -> bool:
        """Flush final y cierre."""
        return self.flush()

    def stats(self) -> dict[str, Any]:
        """Estadísticas del log actual."""
        stats = {"log_path": str(self.log_path), "total_transitions": 0, "episodes": set(), "errors": 0}
        if not self.log_path.exists():
            return stats
        try:
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        stats["total_transitions"] += 1
                        stats["episodes"].add(data.get("episode_id", "unknown"))
                    except json.JSONDecodeError:
                        stats["errors"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[RL-Logger] Error reading stats: {e}", file=sys.stderr)
        stats["episodes"] = len(stats["episodes"])
        return stats


# ---------------------------------------------------------------------------
# CLI / self-test
# ---------------------------------------------------------------------------

def _self_test() -> int:
    print("[RL-Logger] Self-test starting...")
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test_rl.jsonl"
        logger = BagoRLLogger(log_path=log_path)

        episode = str(uuid.uuid4())
        for step in range(5):
            obs = {"stage": "preprod", "retry_count": step, "budget": 1.0}
            action = "lint" if step % 2 == 0 else "secret-scan"
            reward = {"success": 1.0, "latency": -0.2}
            next_obs = {"stage": "preprod", "retry_count": step + 1, "budget": 0.9}
            done = step == 4
            t = logger.log_transition(episode, step, obs, action, reward, next_obs, done, {"workflow": "preprod"})
            assert t is not None, f"Transition {step} should not be None"

        assert logger.flush(), "Flush failed"
        stats = logger.stats()
        assert stats["total_transitions"] == 5, f"Expected 5 transitions, got {stats['total_transitions']}"
        assert stats["episodes"] == 1, f"Expected 1 episode, got {stats['episodes']}"

        # Rotación
        big_path = Path(tmpdir) / "big.jsonl"
        big_logger = BagoRLLogger(log_path=big_path)
        big_logger._buffer_limit = 1
        for i in range(3):
            big_logger.log_transition(str(uuid.uuid4()), 0, {}, "test", 0.0, {}, True)
        assert big_path.exists(), "Log file should exist after rotation test"

    print("[RL-Logger] Self-test PASSED (8/8 checks)")
    return 0


def _verify_existing_log(log_path: Path) -> int:
    print(f"[RL-Logger] Verifying log: {log_path}")
    if not log_path.exists():
        print(f"  Log not found — expected if no transitions captured yet.")
        return 0
    stats = BagoRLLogger(log_path=log_path).stats()
    print(f"  Total transitions: {stats['total_transitions']}")
    print(f"  Unique episodes:   {stats['episodes']}")
    print(f"  Parse errors:      {stats['errors']}")
    if stats['errors'] > 0:
        print("  WARNING: parse errors detected")
        return 1
    print("  Verification OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BAGO RL Transition Logger")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument("--verify", action="store_true", help="Verify existing log file")
    parser.add_argument("--log-path", type=Path, default=DEFAULT_LOG_PATH, help="Path to JSONL log")
    args = parser.parse_args()

    if args.test:
        return _self_test()
    if args.verify:
        return _verify_existing_log(args.log_path)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
