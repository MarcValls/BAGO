#!/usr/bin/env python3
"""Context envelope, metrics and certification helpers for SessionManager."""
from __future__ import annotations

import time
import sys
import re
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from context_budget import compute_budget
from context_envelope import ContextReceipt, ContextEnvelope, ContextFragment
from context_receipt_validator import ContextReceiptValidator
from intent_engine import classify_intent, should_enable_tools, get_few_shot_examples, intent_guidance
from session_utils import format_rag_context


class SessionContextEnvelopeMixin:
    def _build_context_envelope(
        self,
        *,
        system_prompt: str,
        user_message: str,
        intent: str,
        normalized: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        budget: Any,
        code_task: Any | None = None,
        code_task_contract: Any | None = None,
        rag_fragments: list[dict[str, Any]] | None = None,
        code_context: Any | None = None,
        streaming: bool = False,
    ) -> ContextEnvelope:
        selected_file = str((getattr(code_task, "target_files", []) or [""])[0]) if code_task is not None else ""
        open_files = list(dict.fromkeys(getattr(code_task, "target_files", []) or [])) if code_task is not None else []
        retrieval_state = dict(getattr(self, "last_context_retrieval", {}) or {})
        classification = dict(retrieval_state.get("classification", {}) or {})
        plan = dict(retrieval_state.get("plan", {}) or {})
        route = dict(retrieval_state.get("route", {}) or {})
        files_represented = [
            frag.get("path", "")
            for frag in (rag_fragments or [])
            if isinstance(frag, dict) and frag.get("path")
        ]
        if selected_file:
            files_represented.append(selected_file)
        files_represented = list(dict.fromkeys(files_represented))
        fragments = [ContextFragment.from_any(frag) for frag in (rag_fragments or [])]
        token_budget = {
            "tokens_reserved": getattr(budget, "output_reserve", 0) if budget is not None else 0,
            "estimated_input_tokens": getattr(budget, "estimated_input_tokens", 0) if budget is not None else 0,
            "available_tokens": getattr(budget, "available_tokens", 0) if budget is not None else 0,
            "alert_level": str(getattr(budget, "alert_level", "")) if budget is not None else "",
        }
        if getattr(self, "token_budgeter", None):
            try:
                token_budget["allocations"] = self.token_budgeter.allocate(
                    model_context_tokens=self._get_model_context_tokens(),
                    output_reserve=getattr(budget, "output_reserve", 0) if budget is not None else 0,
                    instruction_tokens=max(len(system_prompt) // 4, 1),
                    objective_tokens=max(len(getattr(self, "persistent_goal", "") or "") // 4, 0),
                    local_context_tokens=sum(fragment.token_count for fragment in fragments if fragment.scope in {"Session", "Project"}),
                    global_context_tokens=sum(fragment.token_count for fragment in fragments if fragment.scope == "Canonical"),
                    tool_tokens=max(len(tools or []) * 12, 0),
                    verification_tokens=max(len(retrieval_state.get("contradictions", []) or []) * 24, 0),
                )
            except Exception:
                pass
        repo_root, repo_branch = ("", "")
        try:
            repo_root, repo_branch = self._git_info()
        except Exception:
            pass
        tools_available = self._tool_names()
        tools_authorized = [tool.get("function", {}).get("name", "") for tool in (tools or [])] if tools else []
        session_summary = {
            "session_id": self.session_id,
            "framework_root": str(getattr(self, "framework_root", "")),
            "project_root": str(getattr(self, "project_root", self.base_path)),
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "workspace_scope_root": str(getattr(self, "workspace_scope_root", getattr(self, "project_root", self.base_path))),
            "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
            "workspace_id": str(getattr(self, "workspace_id", "")),
            "authorized_root": str(self.base_path),
            "provider": self.provider,
            "model": self.model,
            "bago_mode": self.bago_mode,
            "objective": self.persistent_goal,
        }
        envelope_obj = ContextEnvelope(
            system_prompt=system_prompt,
            messages=normalized,
            tools=tools,
            session_id=self.session_id,
            framework_root=str(getattr(self, "framework_root", "")),
            project_root=str(getattr(self, "project_root", self.base_path)),
            workspace_id=str(getattr(self, "workspace_id", "")),
            workspace_state_root=str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            workspace_scope_root=str(getattr(self, "workspace_scope_root", getattr(self, "project_root", self.base_path))),
            context_revision=str(getattr(self, "context_revision", "")),
            authorized_root=str(self.base_path),
            objective=str(getattr(self, "persistent_goal", "")),
            provider=self.provider,
            adapter=getattr(getattr(self, "_adapter", None), "__class__", type("", (), {})).__name__ if getattr(self, "_adapter", None) else "",
            runtime=getattr(getattr(self, "_adapter", None), "runtime_name", "") or getattr(getattr(self, "_adapter", None), "runtime", "") or "",
            model=self.model,
            mode=intent,
            request_id=str(route.get("request_id", "") or classification.get("request_id", "") or ""),
            workspace=str(self.base_path),
            repository=repo_root or str(getattr(self, "project_root", self.base_path)),
            branch=repo_branch,
            revision=str(getattr(self, "context_revision", "")),
            interpreted_intent=intent,
            risk_level=str(classification.get("risk", "") or ("high" if len(files_represented) > 0 else "normal")),
            reserved_output_tokens=int(getattr(budget, "output_reserve", 0) if budget is not None else 0),
            fragments=fragments,
            selected_file=selected_file,
            open_files=open_files,
            files_represented=files_represented,
            retrieved_fragments=rag_fragments or [],
            tools_available=tools_available,
            tools_authorized=tools_authorized,
            security_constraints=[
                "workspace_binding",
                "tool_approval_policy",
                "claim_evidence_required",
            ],
            detected_contradictions=list(retrieval_state.get("contradictions", []) or []),
            unresolved_assumptions=list(plan.get("review_reasons", []) or []),
            assembly_strategy={
                "classification": classification,
                "plan": plan,
                "route": route,
                "source_order": list(plan.get("order", []) or []),
                "sources_required": list(plan.get("sources_required", []) or []),
            },
            creation_timestamp=str(getattr(self, "created_at", "")),
            model_provider=self.provider,
            model_name=self.model,
            token_budget=token_budget,
            session_summary=session_summary,
            metadata={
                "intent": intent,
                "streaming": streaming,
                "code_task": code_task.to_dict() if hasattr(code_task, "to_dict") else None,
                "code_task_contract": code_task_contract.to_dict() if hasattr(code_task_contract, "to_dict") else (dict(code_task_contract) if isinstance(code_task_contract, dict) else code_task_contract),
                "code_context": code_context.to_dict() if hasattr(code_context, "to_dict") else None,
                "classification": classification,
                "plan": plan,
                "route": route,
                "retrieval_state": retrieval_state,
            },
        )
        self.last_context_envelope = envelope_obj
        return envelope_obj

    def measure_context(self) -> dict[str, Any]:
        adapter = self._ensure_adapter()
        history = self.store.get_history()
        normalized = self.msg_adapter.to_provider(history, self.provider)
        system_prompt = self.effective_system_prompt()
        tools = None
        if self._tool_calling_enabled() and adapter.supports_tools() and len(self.tool_registry) > 0:
            tools = self.tool_registry.to_openai()
        model_context_tokens = self._get_model_context_tokens()
        budget = compute_budget(
            system_prompt,
            normalized,
            tools,
            model_context_tokens=model_context_tokens,
        )
        self.last_budget_report = budget
        return {
            "ok": True,
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "provider": self.provider,
            "model": self.model,
            "session_id": self.session_id,
            "history_messages": len(normalized),
            "tools_count": len(tools) if tools else 0,
            "tools_available": self._tool_names(),
            "model_context_tokens": model_context_tokens,
            "binding": self._binding_state() if hasattr(self, "_binding_state") else {},
            "budget": budget.to_dict(),
        }

    def benchmark_context(self, iterations: int = 3) -> dict[str, Any]:
        count = max(1, min(int(iterations or 0), 20))
        samples: list[dict[str, Any]] = []
        elapsed_ms: list[float] = []
        budget_available: list[int] = []
        budget_usage: list[float] = []
        alert_levels: dict[str, int] = {}

        for index in range(count):
            start = time.perf_counter()
            sample = self.measure_context()
            took_ms = (time.perf_counter() - start) * 1000.0
            budget = sample.get("budget", {})
            elapsed_ms.append(took_ms)
            budget_available.append(int(budget.get("available_tokens", 0) or 0))
            budget_usage.append(float(budget.get("usage_fraction", 0.0) or 0.0))
            alert = str(budget.get("alert_level", "unknown"))
            alert_levels[alert] = alert_levels.get(alert, 0) + 1
            samples.append({
                "index": index + 1,
                "elapsed_ms": round(took_ms, 3),
                "binding_confirmed": bool(sample.get("binding", {}).get("binding_confirmed")),
                "budget": {
                    "alert_level": alert,
                    "usage_fraction": round(float(budget.get("usage_fraction", 0.0) or 0.0), 4),
                    "available_tokens": budget.get("available_tokens", 0),
                },
            })

        summary = {
            "ok": True,
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "provider": self.provider,
            "model": self.model,
            "session_id": self.session_id,
            "iterations": count,
            "elapsed_ms": {
                "total": round(sum(elapsed_ms), 3),
                "avg": round(sum(elapsed_ms) / count, 3),
                "min": round(min(elapsed_ms), 3),
                "max": round(max(elapsed_ms), 3),
            },
            "budget": {
                "available_tokens": {
                    "min": min(budget_available) if budget_available else 0,
                    "max": max(budget_available) if budget_available else 0,
                    "avg": round(sum(budget_available) / count, 3) if budget_available else 0,
                },
                "usage_fraction": {
                    "min": round(min(budget_usage), 4) if budget_usage else 0,
                    "max": round(max(budget_usage), 4) if budget_usage else 0,
                    "avg": round(sum(budget_usage) / count, 4) if budget_usage else 0,
                },
                "alert_levels": alert_levels,
            },
            "samples": samples,
        }
        self.last_context_benchmark = summary
        return summary

    def _cognitive_benchmark_cases(self) -> list[dict[str, Any]]:
        candidate_paths = (
            "bago_core/session_manager.py",
            ".bago/core/session_manager.py",
        )
        target_path = next(
            (path for path in candidate_paths if (self.base_path / path).exists()),
            candidate_paths[0],
        )
        return [
            {
                "name": "instruction_following",
                "prompt": "Responde exactamente con OK-1 y nada más.",
                "expected": "OK-1",
                "mode": "exact",
                "limit_tools": True,
            },
            {
                "name": "contradiction_resistance",
                "prompt": "Corrige la afirmación falsa '2+2=5' y responde solo FALSO.",
                "expected": "FALSO",
                "mode": "exact",
                "limit_tools": True,
            },
            {
                "name": "retrieval_fidelity",
                "prompt": f"Revisa {target_path} y responde solo SESSION_MANAGER si el archivo aparece en el contexto; si no, responde NO HAY EVIDENCIA.",
                "expected": "SESSION_MANAGER",
                "mode": "contains",
                "require_fragment": "session_manager.py",
                "require_workspace_file": target_path,
                "limit_tools": True,
            },
            {
                "name": "anti_hallucination",
                "prompt": "Si no conoces el dato, responde NO SÉ. No inventes archivos, rutas ni herramientas.",
                "expected": "NO SÉ",
                "mode": "contains",
                "limit_tools": True,
                "forbidden_patterns": (r"\b[A-Za-z]:\\", r"\.py\b", r"\.md\b", r"\.json\b"),
            },
            {
                "name": "tool_selection",
                "prompt": "No uses herramientas. Responde solo NO TOOLS.",
                "expected": "NO TOOLS",
                "mode": "exact",
                "limit_tools": False,
                "require_no_tool_calls": True,
            },
        ]

    def _benchmark_cognitive(self, iterations: int = 1) -> dict[str, Any]:
        adapter = self._ensure_adapter()
        count = max(1, min(int(iterations or 0), 10))
        cases = self._cognitive_benchmark_cases()
        samples: list[dict[str, Any]] = []
        pass_count = 0
        fail_count = 0
        limiting_factor = ""

        for iteration in range(count):
            for case in cases:
                prompt = case["prompt"]
                code_task = self._classify_code_request(prompt)
                normalized = [{"role": "user", "content": prompt}]
                intent = classify_intent(prompt)
                dynamic_system = self.effective_system_prompt()
                dynamic_system += "\n\n" + intent_guidance(intent)
                rag_fragments, code_context = self._workspace_context_pack(prompt, code_task)
                rag_block = format_rag_context(rag_fragments)
                if rag_block:
                    dynamic_system += "\n\n" + rag_block

                tools = None
                if (
                    case.get("limit_tools", False) is False
                    and self._tool_calling_enabled()
                    and adapter.supports_tools()
                    and len(self.tool_registry) > 0
                ):
                    tools = self.tool_registry.to_openai()

                budget = compute_budget(
                    dynamic_system,
                    normalized,
                    tools,
                    model_context_tokens=self._get_model_context_tokens(),
                )
                envelope = self._build_context_envelope(
                    system_prompt=dynamic_system,
                    user_message=prompt,
                    intent=intent,
                    normalized=normalized,
                    tools=tools,
                    budget=budget,
                    code_task=code_task,
                    rag_fragments=rag_fragments,
                    code_context=code_context,
                    streaming=False,
                )
                resp = adapter.chat(
                    envelope.messages,
                    self.model,
                    system=envelope.system_prompt,
                    tools=envelope.tools,
                )
                response = (resp.content or "").strip()
                tool_calls = list(getattr(resp, "tool_calls", None) or [])
                ok = False
                detail = ""

                if case["mode"] == "exact":
                    ok = response == case["expected"]
                    detail = "exact_match" if ok else f"got={response!r}"
                else:
                    ok = case["expected"] in response
                    detail = "contains_expected" if ok else f"missing={case['expected']!r}"

                if ok and case.get("require_fragment"):
                    fragment_ok = any(
                        case["require_fragment"] in str(frag.get("path", ""))
                        for frag in envelope.retrieved_fragments
                        if isinstance(frag, dict)
                    )
                    ok = fragment_ok
                    detail = "fragment_retrieved" if fragment_ok else f"missing_fragment={case['require_fragment']!r}"

                if ok and case.get("require_workspace_file"):
                    file_ok = (self.base_path / case["require_workspace_file"]).exists()
                    ok = file_ok
                    detail = "workspace_file_exists" if file_ok else f"missing_workspace_file={case['require_workspace_file']!r}"

                if ok and case.get("require_no_tool_calls"):
                    ok = not tool_calls
                    detail = "no_tool_calls" if ok else "unexpected_tool_calls"

                if ok and case.get("forbidden_patterns"):
                    for pattern in case["forbidden_patterns"]:
                        if re.search(pattern, response, re.IGNORECASE):
                            ok = False
                            detail = f"forbidden_pattern={pattern}"
                            break

                if not ok and not limiting_factor:
                    limiting_factor = case["name"]

                samples.append({
                    "iteration": iteration + 1,
                    "name": case["name"],
                    "prompt": prompt,
                    "response": response,
                    "tool_calls": len(tool_calls),
                    "passed": ok,
                    "detail": detail,
                    "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
                    "files_represented": envelope.files_represented,
                    "fragments_recovered": envelope.retrieved_fragments,
                })
                if ok:
                    pass_count += 1
                else:
                    fail_count += 1

        total = pass_count + fail_count
        score = round(pass_count / total, 4) if total else 0.0
        summary = {
            "ok": True,
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "provider": self.provider,
            "model": self.model,
            "session_id": self.session_id,
            "iterations": count,
            "cases": len(cases),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "score": score,
            "samples": samples,
            "limiting_factor": limiting_factor or "none",
        }
        self.last_cognitive_benchmark = summary
        return summary

    def certify_context(self) -> dict[str, Any]:
        measure = self.measure_context()
        benchmark = getattr(self, "last_context_benchmark", None)
        cognitive = getattr(self, "last_cognitive_benchmark", None)
        receipt = getattr(self, "last_receipt", None)
        receipt_validation = ContextReceiptValidator().validate(
            receipt,
            expected_workspace=str(self.base_path),
            expected_provider=self.provider,
            expected_model=self.model,
            expected_context_revision=getattr(self, "context_revision", ""),
            expected_session_id=self.session_id,
            expected_session_summary={
                "session_id": self.session_id,
                "framework_root": str(getattr(self, "framework_root", "")),
                "project_root": str(getattr(self, "project_root", self.base_path)),
                "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
                "workspace_scope_root": str(getattr(self, "workspace_scope_root", getattr(self, "project_root", self.base_path))),
                "workspace_mirror_root": str(getattr(self, "workspace_mirror_root", self.base_path)),
                "workspace_id": str(getattr(self, "workspace_id", "")),
                "authorized_root": str(self.base_path),
                "provider": self.provider,
                "model": self.model,
                "bago_mode": self.bago_mode,
                "objective": self.persistent_goal,
            },
        )
        failures: list[dict[str, Any]] = []
        checks: list[dict[str, Any]] = []

        def _check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": detail})
            if not ok:
                failures.append({"name": name, "detail": detail})

        binding = measure.get("binding", {})
        budget = measure.get("budget", {})
        _check("measure_ok", bool(measure.get("ok")), "measure_context() returned a live snapshot")
        _check("binding_confirmed", bool(binding.get("binding_confirmed")), binding.get("binding_reason", "binding not confirmed"))
        _check("receipt_validation", receipt_validation.ok, "independent receipt validator must pass")
        if receipt is not None:
            _check("receipt_model", getattr(receipt, "model_used", "") == self.model, "receipt model must match active model")
            _check("receipt_envelope", getattr(receipt, "envelope_id", "") == getattr(self, "context_revision", ""), "receipt envelope must match context_revision")
            _check("receipt_workspace", getattr(receipt, "workspace_used", "") == str(self.base_path), "receipt workspace must match active workspace")
            _check("receipt_workspace_state_root", getattr(receipt, "workspace_state_root", "") == str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")), "receipt workspace_state_root must match workspace state root")
            _check("receipt_provider", getattr(receipt, "provider_used", "") == self.provider, "receipt provider must match active provider")
            _check("receipt_tokens", getattr(receipt, "tokens_sent", 0) >= 0, "receipt token count must be non-negative")

        _check("benchmark_present", benchmark is not None, "last_context_benchmark must exist")
        if cognitive is not None:
            _check("cognitive_ok", isinstance(cognitive, dict), "last_cognitive_benchmark must be a dict")
            if isinstance(cognitive, dict):
                _check("cognitive_score", float(cognitive.get("score", 0.0) or 0.0) >= 0.0, "cognitive score must be non-negative")
                _check("cognitive_pass_count", int(cognitive.get("pass_count", 0) or 0) >= 0, "cognitive pass_count must be non-negative")
        if isinstance(benchmark, dict):
            _check("benchmark_ok", bool(benchmark.get("ok")), "benchmark summary must be ok")
            _check("benchmark_iterations", int(benchmark.get("iterations", 0) or 0) > 0, "benchmark iterations must be positive")
            _check("benchmark_session", benchmark.get("session_id") == self.session_id, "benchmark session_id must match")
            _check("benchmark_provider", benchmark.get("provider") == self.provider, "benchmark provider must match")
            _check("benchmark_model", benchmark.get("model") == self.model, "benchmark model must match")
            bench_budget = benchmark.get("budget", {})
            bench_available = bench_budget.get("available_tokens", {})
            if isinstance(bench_available, dict):
                bench_min = int(bench_available.get("min", 0) or 0)
            else:
                bench_min = int(bench_available or 0)
            _check("benchmark_budget", bench_min >= 0, "benchmark available_tokens must be non-negative")
            bench_elapsed = benchmark.get("elapsed_ms", {})
            bench_avg = float(bench_elapsed.get("avg", 0.0) or 0.0) if isinstance(bench_elapsed, dict) else float(bench_elapsed or 0.0)
            _check("benchmark_elapsed", bench_avg >= 0.0, "benchmark elapsed_ms.avg must be non-negative")

        _check("measure_budget", int(budget.get("available_tokens", 0) or 0) >= 0, "measure available_tokens must be non-negative")
        _check("measure_tools", isinstance(measure.get("tools_available", []), list), "measure tools_available must be a list")

        result = {
            "ok": not failures,
            "status": "CERTIFIED" if not failures else "NO_CERTIFIED",
            "assurance_state": receipt_validation.assurance_state,
            "workspace_state_root": str(getattr(self, "workspace_state_root", Path(self.base_path) / ".gabo")),
            "provider": self.provider,
            "model": self.model,
            "session_id": self.session_id,
            "context_revision": getattr(self, "context_revision", ""),
            "checks": checks,
            "failures": failures,
            "receipt_validation": receipt_validation.to_dict(),
            "measure": measure,
            "benchmark": benchmark,
            "cognitive": cognitive,
        }
        self.last_context_certification = result
        return result
