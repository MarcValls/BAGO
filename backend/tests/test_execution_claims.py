from __future__ import annotations

import threading
import multiprocessing
import os

import pytest


def _sqlite_claim_worker(db_path: str, barrier, queue, owner: str) -> None:
    from execution_claims import SQLiteExecutionClaimStore

    store = SQLiteExecutionClaimStore(db_path)
    barrier.wait(timeout=10)
    claim = store.try_acquire("workspace:shared", owner, f"op-{owner}", lease_seconds=30)
    queue.put((owner, claim.fencing_token if claim else None))


def _postgres_claim_worker(dsn: str, resource_key: str, barrier, queue, owner: str) -> None:
    from execution_claims import PostgresExecutionClaimStore

    store = PostgresExecutionClaimStore(dsn)
    barrier.wait(timeout=20)
    claim = store.try_acquire(resource_key, owner, f"op-{owner}", lease_seconds=30)
    queue.put((owner, claim.fencing_token if claim else None))


def test_claims_are_exclusive_per_resource_and_independent_between_resources():
    from execution_claims import InMemoryExecutionClaimStore

    store = InMemoryExecutionClaimStore()
    first = store.try_acquire("file:C:/repo/a.txt", "worker-a", "op-1")
    assert first is not None
    assert store.try_acquire("file:C:/repo/a.txt", "worker-b", "op-2") is None
    unrelated = store.try_acquire("file:C:/repo/b.txt", "worker-b", "op-2")
    assert unrelated is not None
    assert first.fencing_token == unrelated.fencing_token == 1

    assert store.release(first)
    replacement = store.try_acquire("file:C:/repo/a.txt", "worker-b", "op-3")
    assert replacement is not None
    assert replacement.fencing_token == 2


def test_expiry_advances_fencing_and_rejects_the_previous_owner():
    from execution_claims import ExecutionClaimError, InMemoryExecutionClaimStore

    now = [100.0]
    store = InMemoryExecutionClaimStore(clock=lambda: now[0])
    stale = store.try_acquire("workspace:one", "worker-a", "op-1", lease_seconds=5)
    assert stale is not None
    now[0] = 106.0

    assert store.expire() == 1
    assert not store.validate(stale)
    current = store.try_acquire("workspace:one", "worker-b", "op-2", lease_seconds=5)
    assert current is not None
    assert current.fencing_token == stale.fencing_token + 1
    assert not store.release(stale)
    with pytest.raises(ExecutionClaimError) as rejected:
        store.execute_if_valid(stale, lambda: "must not run")
    assert rejected.value.code == "execution_claim_stale"


def test_renew_extends_only_a_live_claim_and_release_is_terminal():
    from execution_claims import InMemoryExecutionClaimStore

    now = [200.0]
    store = InMemoryExecutionClaimStore(clock=lambda: now[0])
    claim = store.try_acquire("service:catalog", "worker-a", "op-1", lease_seconds=5)
    assert claim is not None
    now[0] = 204.0
    renewed = store.renew(claim, lease_seconds=10)
    assert renewed is not None
    assert renewed.lease_until == 214.0
    assert store.validate(renewed)
    assert store.release(renewed)
    assert not store.validate(renewed)
    now[0] = 220.0
    assert store.renew(renewed, lease_seconds=10) is None


def test_expired_claim_cannot_be_replaced_while_its_effect_is_in_progress():
    from execution_claims import InMemoryExecutionClaimStore

    now = [300.0]
    store = InMemoryExecutionClaimStore(clock=lambda: now[0])
    claim = store.try_acquire("file:C:/repo/slow.txt", "worker-a", "op-1", lease_seconds=1)
    assert claim is not None
    entered = threading.Event()
    resume = threading.Event()

    def effect():
        entered.set()
        assert resume.wait(timeout=3)
        return "done"

    result: list[str] = []
    thread = threading.Thread(target=lambda: result.append(store.execute_if_valid(claim, effect)))
    thread.start()
    assert entered.wait(timeout=3)
    now[0] = 302.0
    assert store.expire() == 0
    assert store.try_acquire("file:C:/repo/slow.txt", "worker-b", "op-2") is None
    resume.set()
    thread.join(timeout=3)
    assert result == ["done"]
    assert store.release(claim)
    replacement = store.try_acquire("file:C:/repo/slow.txt", "worker-b", "op-2")
    assert replacement is not None
    assert replacement.fencing_token == claim.fencing_token + 1


def test_plan_execution_records_claim_identity_and_fencing_evidence(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import authorization_boundary as auth
    from authorization_boundary import AuthorizationBoundary
    from effect_registry import REGISTRY
    from execution_gateway import ExecutionContext, ExecutionGateway
    from execution_request import build_execution_request
    from plan_engine import PlanEngine
    from governed_work_pipeline import plan_execution_target

    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Plan con claim", "1. Crear archivo notes/claimed.txt con contenido: claim"
    )
    engine.register_plan(plan)
    manager = SimpleNamespace(
        base_path=tmp_path,
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        session_id="session-claim",
        plan_engine=engine,
    )
    boundary = AuthorizationBoundary()
    request = build_execution_request(
        effect_id="plan.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.execution-claim",
        target=plan_execution_target(plan),
        arguments={},
        scope=REGISTRY.get("plan.execute").default_scope,
        policy_version=REGISTRY.digest,
    )
    challenge = boundary.create_challenge(request, interaction_id="interaction-claim")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-claim",
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]
    gateway = ExecutionGateway(boundary)

    result, _ = gateway.execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is True
    outcome = next(iter(plan.governed_work["outcomes"].values()))
    assert outcome["execution_claim_id"]
    assert outcome["execution_resource_key"].endswith("notes\\claimed.txt")
    assert outcome["execution_fencing_token"] == "1"
    assert outcome["execution_claim_durability"] == "process-local"
    assert any(item.startswith("execution_fencing_token:1") for item in outcome["evidence"])


def test_gateway_rejects_expired_claim_before_material_child_effect(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import authorization_boundary as auth
    from authorization_boundary import AuthorizationBoundary
    from effect_registry import REGISTRY
    from execution_claims import InMemoryExecutionClaimStore
    from execution_gateway import ExecutionContext, ExecutionGateway
    from execution_request import build_execution_request
    from governed_work_pipeline import plan_execution_target
    from plan_engine import PlanEngine

    now = [400.0]

    class ExpiresImmediatelyAfterAcquire(InMemoryExecutionClaimStore):
        def try_acquire(self, *args, **kwargs):
            claim = super().try_acquire(*args, **kwargs)
            now[0] += 61.0
            return claim

    monkeypatch.setattr(auth, "state_root", lambda: tmp_path / "auth")
    engine = PlanEngine()
    plan = engine.create_plan_with_actions(
        "Plan con claim caducado",
        "1. Crear archivo notes/stale-claim.txt con contenido: no",
    )
    engine.register_plan(plan)
    manager = SimpleNamespace(
        base_path=tmp_path,
        project_root=tmp_path,
        workspace_scope_root=tmp_path,
        workspace_mirror_root=tmp_path,
        session_id="session-stale-claim",
        plan_engine=engine,
    )
    boundary = AuthorizationBoundary()
    request = build_execution_request(
        effect_id="plan.execute",
        actor_kind="user",
        principal_id="interactive-local-user",
        session_id=manager.session_id,
        source_surface="test.execution-claim-stale",
        target=plan_execution_target(plan),
        arguments={},
        scope=REGISTRY.get("plan.execute").default_scope,
        policy_version=REGISTRY.digest,
    )
    challenge = boundary.create_challenge(request, interaction_id="interaction-stale-claim")
    permit = boundary.approve_challenge(
        challenge_id=challenge["challenge_id"],
        interaction_id="interaction-stale-claim",
        session_id=request.session_id,
        channel="ui-react",
    )["permit"]
    store = ExpiresImmediatelyAfterAcquire(clock=lambda: now[0])
    gateway = ExecutionGateway(boundary, claim_store=store)

    result, _ = gateway.execute(
        permit_token=permit["token"],
        request=request,
        context=ExecutionContext(manager=manager),
    )

    assert result["ok"] is False
    assert result["block_code"] == "pipeline_outcome_unknown"
    outcome = next(iter(plan.governed_work["outcomes"].values()))
    assert outcome["outcome_status"] == "OUTCOME_UNKNOWN"
    assert not (tmp_path / "notes" / "stale-claim.txt").exists()


def test_sqlite_claim_survives_store_restart_and_fencing_generation_is_durable(tmp_path):
    from execution_claims import SQLiteExecutionClaimStore

    db_path = tmp_path / "state" / "execution_claims.sqlite3"
    first_store = SQLiteExecutionClaimStore(db_path)
    first = first_store.try_acquire("file:/repo/a.txt", "worker-a", "op-a")
    assert first is not None

    restarted_store = SQLiteExecutionClaimStore(db_path)
    assert restarted_store.validate(first)
    assert restarted_store.try_acquire("file:/repo/a.txt", "worker-b", "op-b") is None
    assert restarted_store.release(first)
    replacement = restarted_store.try_acquire("file:/repo/a.txt", "worker-b", "op-b")
    assert replacement is not None
    assert replacement.fencing_token == first.fencing_token + 1


def test_gateway_uses_sqlite_under_session_manager_state_root(tmp_path):
    from types import SimpleNamespace

    from execution_claims import SQLiteExecutionClaimStore
    from execution_gateway import ExecutionGateway

    gateway = ExecutionGateway()
    manager = SimpleNamespace(state_root=tmp_path / "canonical-state")
    store = gateway.claim_store_for(manager)

    assert isinstance(store, SQLiteExecutionClaimStore)
    assert store is gateway.claim_store_for(manager)
    assert store.db_path == (manager.state_root / "execution_claims.sqlite3").resolve()


def test_sqlite_expired_lease_can_be_recovered_after_restart(tmp_path):
    from execution_claims import SQLiteExecutionClaimStore

    now = [500.0]
    db_path = tmp_path / "execution_claims.sqlite3"
    owner_store = SQLiteExecutionClaimStore(db_path, clock=lambda: now[0])
    stale = owner_store.try_acquire("job:recover", "worker-a", "op-a", lease_seconds=5)
    assert stale is not None

    now[0] = 506.0
    recovery_store = SQLiteExecutionClaimStore(db_path, clock=lambda: now[0])
    assert recovery_store.expire() == 1
    recovered = recovery_store.try_acquire("job:recover", "worker-b", "op-b")
    assert recovered is not None
    assert recovered.fencing_token == stale.fencing_token + 1
    assert not recovery_store.validate(stale)


def test_sqlite_does_not_transfer_claim_during_material_callback(tmp_path):
    from execution_claims import SQLiteExecutionClaimStore

    now = [700.0]
    db_path = tmp_path / "execution_claims.sqlite3"
    owner_store = SQLiteExecutionClaimStore(db_path, clock=lambda: now[0])
    replacement_store = SQLiteExecutionClaimStore(db_path, clock=lambda: now[0])
    stale = owner_store.try_acquire("file:/repo/slow.txt", "worker-a", "op-a", lease_seconds=1)
    assert stale is not None
    entered = threading.Event()
    resume = threading.Event()
    effect_result: list[str] = []

    def effect():
        entered.set()
        assert resume.wait(timeout=5)
        return "committed"

    effect_thread = threading.Thread(
        target=lambda: effect_result.append(owner_store.execute_if_valid(stale, effect))
    )
    effect_thread.start()
    assert entered.wait(timeout=5)
    now[0] = 702.0
    replacement: list[object] = []
    acquire_thread = threading.Thread(
        target=lambda: replacement.append(
            replacement_store.try_acquire("file:/repo/slow.txt", "worker-b", "op-b")
        )
    )
    acquire_thread.start()
    acquire_thread.join(timeout=0.1)
    assert acquire_thread.is_alive()
    resume.set()
    effect_thread.join(timeout=5)
    acquire_thread.join(timeout=5)

    assert effect_result == ["committed"]
    assert len(replacement) == 1
    assert replacement[0] is not None
    assert replacement[0].fencing_token == stale.fencing_token + 1


def test_sqlite_store_allows_only_one_simultaneous_acquisition_across_processes(tmp_path):
    db_path = tmp_path / "execution_claims.sqlite3"
    from execution_claims import SQLiteExecutionClaimStore

    SQLiteExecutionClaimStore(db_path)
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    workers = [
        context.Process(target=_sqlite_claim_worker, args=(str(db_path), barrier, queue, owner))
        for owner in ("worker-a", "worker-b")
    ]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=20) for _ in workers]
    for worker in workers:
        worker.join(timeout=20)
        assert worker.exitcode == 0

    assert sum(token is not None for _, token in results) == 1
    assert sorted(token for _, token in results if token is not None) == [1]


def test_postgres_store_coordinates_processes_when_integration_database_is_configured():
    dsn = os.environ.get("BAGO_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("BAGO_TEST_POSTGRES_DSN is not configured")
    pytest.importorskip("psycopg")
    from execution_claims import PostgresExecutionClaimStore

    import uuid

    store = PostgresExecutionClaimStore(dsn)
    resource_key = f"workspace:postgres-shared:{uuid.uuid4()}"
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    queue = context.Queue()
    workers = [
        context.Process(target=_postgres_claim_worker, args=(dsn, resource_key, barrier, queue, owner))
        for owner in ("worker-a", "worker-b")
    ]
    for worker in workers:
        worker.start()
    results = [queue.get(timeout=45) for _ in workers]
    for worker in workers:
        worker.join(timeout=45)
        assert worker.exitcode == 0
    winners = [token for _, token in results if token is not None]
    assert len(winners) == 1
    assert store.requires_sink_fencing is True
    assert store.durability == "durable-distributed-claims"


def test_filesystem_write_is_atomic_and_replay_of_same_content_is_idempotent(tmp_path):
    from types import SimpleNamespace

    from filesystem_effects import write_file_effect

    manager = SimpleNamespace(project_root=tmp_path)
    first = write_file_effect(manager, "notes/result.txt", "stable payload")
    second = write_file_effect(manager, "notes/result.txt", "stable payload")

    target = tmp_path / "notes" / "result.txt"
    assert target.read_bytes() == b"stable payload"
    assert first["receipt_id"] == second["receipt_id"]
    assert list(target.parent.glob("*.tmp")) == []
