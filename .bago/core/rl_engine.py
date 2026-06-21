#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
rl_engine.py — BAGO 4.1.5 Reinforcement Learning Engine

Módulo de aprendizaje por refuerzo ligero para BAGO:
- Feedback implícito/explícito del usuario sobre respuestas
- Aprendizaje de preferencias entre providers/modelos
- Sugerencia automática de provider óptimo según el contexto
- No dependencias externas (puro Python + JSON Lines)

Arquitectura atómica:
- RewardStore: persistencia de recompensas
- PreferenceModel: aprendizaje de preferencias por (provider, modelo, fingerprint_tarea)
- RLPolicy: política de selección epsilon-greedy + UCB
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

from state_paths import resolve_state_root

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class RewardStore:
    """Persistencia append-only de recompensas por interacción."""

    def __init__(self, base_dir: Path | str | None = None, state_root: str | Path | None = None):
        root = resolve_state_root(state_root if state_root is not None else base_dir)
        self.base_dir = root / "rl"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._file = self.base_dir / "rewards.jsonl"

    def append(
        self,
        session_id: str,
        provider: str,
        model: str,
        reward: float,
        fingerprint: str = "",
        metadata: dict | None = None,
    ) -> None:
        entry = {
            "ts": time.time(),
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "reward": reward,
            "fingerprint": fingerprint,
            "meta": metadata or {},
        }
        with open(self._file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self._file.exists():
            return []
        out = []
        with open(self._file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


class PreferenceModel:
    """Aprendizaje de preferencias por combinación (provider, model, fingerprint)."""

    def __init__(self, base_dir: Path | str | None = None, state_root: str | Path | None = None):
        self.store = RewardStore(base_dir, state_root=state_root)
        self._cache: dict[str, dict] = {}
        self._dirty = True

    def _key(self, provider: str, model: str, fingerprint: str) -> str:
        return f"{provider}::{model}::{fingerprint}"

    def _rebuild_cache(self) -> None:
        if not self._dirty:
            return
        self._cache.clear()
        for entry in self.store.read_all():
            key = self._key(entry["provider"], entry["model"], entry.get("fingerprint", ""))
            bucket = self._cache.setdefault(key, {"n": 0, "sum": 0.0, "last_ts": 0})
            bucket["n"] += 1
            bucket["sum"] += entry["reward"]
            bucket["last_ts"] = max(bucket["last_ts"], entry["ts"])
        self._dirty = False

    def _stats(self, provider: str, model: str, fingerprint: str = "") -> dict[str, float | int]:
        self._rebuild_cache()
        if fingerprint:
            bucket = self._cache.get(self._key(provider, model, fingerprint))
            if bucket:
                return dict(bucket)

        prefix = f"{provider}::{model}::"
        stats = {"n": 0, "sum": 0.0, "last_ts": 0}
        for key, bucket in self._cache.items():
            if key.startswith(prefix):
                stats["n"] += bucket["n"]
                stats["sum"] += bucket["sum"]
                stats["last_ts"] = max(stats["last_ts"], bucket["last_ts"])
        return stats

    def score(self, provider: str, model: str, fingerprint: str = "") -> float:
        bucket = self._stats(provider, model, fingerprint)
        if bucket["n"] == 0:
            return 0.0
        return bucket["sum"] / bucket["n"]

    def observations(self, provider: str, model: str, fingerprint: str = "") -> int:
        bucket = self._stats(provider, model, fingerprint)
        return int(bucket["n"])

    def add_reward(
        self,
        session_id: str,
        provider: str,
        model: str,
        reward: float,
        fingerprint: str = "",
        metadata: dict | None = None,
    ) -> None:
        self.store.append(session_id, provider, model, reward, fingerprint, metadata)
        self._dirty = True

    def best(self, fingerprint: str = "", candidates: list[tuple[str, str]] | None = None) -> tuple[str, str] | None:
        """Devuelve el (provider, model) con mayor score para un fingerprint."""
        self._rebuild_cache()
        if not candidates:
            return None
        best_score = -1e9
        best_observations = -1
        best_pair: tuple[str, str] | None = None
        for provider, model in candidates:
            n = self.observations(provider, model, fingerprint)
            if n <= 0:
                continue
            s = self.score(provider, model, fingerprint)
            if s > best_score or (s == best_score and n > best_observations):
                best_score = s
                best_observations = n
                best_pair = (provider, model)
        return best_pair


class RLPolicy:
    """Política de selección epsilon-greedy + UCB1."""

    def __init__(
        self,
        preference: PreferenceModel,
        epsilon: float = 0.15,
        ucb_c: float = 1.414,
    ):
        self.pref = preference
        self.epsilon = epsilon
        self.ucb_c = ucb_c

    def select(
        self,
        candidates: list[tuple[str, str]],
        fingerprint: str = "",
    ) -> tuple[str, str]:
        if not candidates:
            raise ValueError("No candidates")

        if random.random() < self.epsilon:
            return random.choice(candidates)

        # UCB1 score = avg_reward + c * sqrt(log(total_n) / n_i)
        total_n = sum(
            self.pref.observations(p, m, fingerprint) for p, m in candidates
        )
        total_n = max(total_n, 1.0)

        best_score = -1e9
        best_pair = candidates[0]
        for provider, model in candidates:
            avg = self.pref.score(provider, model, fingerprint)
            key = self.pref._key(provider, model, fingerprint)
            n = self.pref._cache.get(key, {}).get("n", 0)
            exploration = self.ucb_c * math.sqrt(math.log(total_n + 1) / (n + 1))
            score = avg + exploration
            if score > best_score:
                best_score = score
                best_pair = (provider, model)

        return best_pair


class FeedbackCollector:
    """Helper para convertir interacciones en recompensas."""

    def __init__(self, preference: PreferenceModel):
        self.pref = preference

    def implicit(
        self,
        session_id: str,
        provider: str,
        model: str,
        user_message: str,
        response: str,
        response_time_ms: float,
        tokens_used: int,
    ) -> float:
        """Calcula recompensa implícita basada en heurísticas."""
        reward = 0.0
        # Rapidez
        if response_time_ms < 2000:
            reward += 0.3
        elif response_time_ms < 5000:
            reward += 0.1
        else:
            reward -= 0.2

        # Longitud adecuada (no muy corta, no muy larga)
        resp_len = len(response.split())
        if 10 <= resp_len <= 200:
            reward += 0.2
        elif resp_len < 5:
            reward -= 0.1

        # Sin error
        if response.startswith("Error") or response.startswith("BAGO Error"):
            reward -= 0.5
        else:
            reward += 0.2

        fingerprint = self._fingerprint(user_message)
        self.pref.add_reward(session_id, provider, model, reward, fingerprint)
        return reward

    def explicit(
        self,
        session_id: str,
        provider: str,
        model: str,
        user_message: str,
        rating: float,  # -1.0 a 1.0
    ) -> None:
        """Registra feedback explícito del usuario."""
        fingerprint = self._fingerprint(user_message)
        self.pref.add_reward(session_id, provider, model, rating, fingerprint)

    @staticmethod
    def _fingerprint(text: str) -> str:
        """Fingerprint simple por longitud + primeras 3 palabras."""
        words = re.findall(r"\w+", text.lower())[:3]
        head = "_".join(words) if words else "global"
        return f"{head}_{len(text.strip())}"

    def fingerprint_for(self, text: str) -> str:
        return self._fingerprint(text)


# ── Quick test ────────────────────────────────────────────────────────

def _run_tests() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        state_root = Path(td) / "state"
        old = os.environ.get("BAGO_STATE_ROOT")
        os.environ["BAGO_STATE_ROOT"] = str(state_root)
        # RewardStore
        store = RewardStore(td)
        store.append("s1", "ollama-local", "llama3.2:3b", 0.8, "hola_10")
        store.append("s1", "ollama-local", "llama3.2:1b", 0.4, "hola_10")
        all_rewards = store.read_all()
        assert len(all_rewards) == 2
        assert all_rewards[0]["reward"] == 0.8

        # PreferenceModel
        pm = PreferenceModel(td)
        # La cache debe reconstruirse desde disco al arrancar en frio
        assert abs(pm.score("ollama-local", "llama3.2:3b", "hola_10") - 0.8) < 0.01
        pm.store._file.write_text("")
        pm._dirty = True
        pm.add_reward("s1", "ollama-local", "llama3.2:3b", 0.8, "hola_10")
        pm.add_reward("s1", "ollama-local", "llama3.2:3b", 0.9, "hola_10")
        pm.add_reward("s1", "ollama-local", "llama3.2:1b", 0.3, "hola_10")
        assert abs(pm.score("ollama-local", "llama3.2:3b", "hola_10") - 0.85) < 0.01
        assert abs(pm.score("ollama-local", "llama3.2:3b") - 0.85) < 0.01
        assert pm.best("", [("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")]) == ("ollama-local", "llama3.2:3b")
        assert pm.best("", [("openrouter", "nous/hermes-3")]) is None

        best = pm.best("hola_10", [("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")])
        assert best == ("ollama-local", "llama3.2:3b")

        # RLPolicy
        policy = RLPolicy(pm, epsilon=0.0, ucb_c=1.414)
        selected = policy.select(
            [("ollama-local", "llama3.2:3b"), ("ollama-local", "llama3.2:1b")],
            "hola_10",
        )
        assert selected == ("ollama-local", "llama3.2:3b")

        # FeedbackCollector implicit
        fc = FeedbackCollector(pm)
        r = fc.implicit("s2", "ollama-local", "llama3.2:3b", "hola", "OK todo bien", 1500, 42)
        assert isinstance(r, float)
        assert -1.0 <= r <= 1.0

        # FeedbackCollector explicit
        fc.explicit("s2", "ollama-local", "llama3.2:3b", "hola", 1.0)
        assert pm.score("ollama-local", "llama3.2:3b", "hola_4") >= 0.0

    print("rl_engine.py --test: ALL PASS")
    if old is None:
        os.environ.pop("BAGO_STATE_ROOT", None)
    else:
        os.environ["BAGO_STATE_ROOT"] = old
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
