# Agentic Data Lab: OpenTelemetry and Jaeger case

This BAGO portfolio integration runs the existing Bruma Market governed E2E
case from the sibling `BAGO_AGENTIC_DATA_LAB` checkout. The lab remains the
owner of its agent, local evidence trace, OpenTelemetry bridge and Jaeger
validation; this repository supplies a repeatable entry point and retains the
current-run receipt under `.run/agentic-data-lab-jaeger/`.

## What the case shows

```text
governed agent run
  -> retrieval and evidence references
  -> permit / authorization result
  -> execution and receipts
  -> LocalTrace
  -> OpenTelemetry parent/child spans
  -> OTLP/HTTP to local Jaeger
  -> Jaeger query confirms this run and its operations
```

The trace preserves `run_id`, `event_id`, sequence, status and evidence
references as span attributes. Parent relationships preserve the run's event
tree. Jaeger is a searchable observability projection; it is not BAGO's source
of truth, an authorization mechanism or a production collector.

## Run and view

From the BAGO repository root in PowerShell:

```powershell
./scripts/run-agentic-data-lab-jaeger-demo.ps1
```

The default lab path is the sibling directory `../BAGO_AGENTIC_DATA_LAB`. The
launcher starts its pinned local Jaeger Compose service, executes the lab's
live validator with its existing virtual environment, verifies the trace via
Jaeger's query API, and writes the current output to:

```text
.run/agentic-data-lab-jaeger/live-validation.json
```

Open [Jaeger](http://localhost:16686), select service
`bago-agentic-data-lab`, and search traces. The validation receipt also prints
the current run's Jaeger trace ID and observed operations. The collector stays
up for inspection; stop it when finished:

```powershell
docker compose -p bago-otel -f ../BAGO_AGENTIC_DATA_LAB/infra/observability/docker-compose.yml down
```

Pass `-LabRoot <path>` if the lab checkout lives elsewhere.

## BAGO ExecutionGateway runtime trace

BAGO also has an opt-in trace at its actual execution boundary. It creates
spans for the server-policy authorization decision, `ExecutionGateway`, the
resolved adapter and the outbound HTTP request. These spans attach
`request_id`, `parent_execution_id`, effect/fingerprint digests and available
decision, permit and receipt IDs. Raw arguments, permit tokens and full target
paths are excluded. Since the current Gateway contract has no canonical
cross-request `run_id`, the trace uses `request_id` and the existing parent
execution link; it does not relabel either as a run ID.

Install the optional pinned OpenTelemetry packages once, then start local
Jaeger with the Compose command above and run this read-only Gateway case:

```powershell
python -m pip install -r backend/requirements-observability.txt
python scripts/run-bago-gateway-observability-demo.py
```

The case calls Jaeger's local services endpoint through BAGO's existing
server-policy `network.read` effect. It uses no user Permit and that effect
does not issue a BAGO material-effect receipt, so `permit_id` and `receipt_id`
are correctly absent in this trace; the policy decision ID is present. The
trace includes `bago.external.http` as a client span. W3C `traceparent`
propagation is enabled only for this local demo request. The resulting trace
ID and request ID are written to
`.run/agentic-data-lab-jaeger/bago-gateway-trace-observation.json`.

For BAGO's regular runtime, enable the exporter with
`BAGO_OTEL_ENABLED=1` and set `BAGO_OTEL_ENDPOINT` to an OTLP/HTTP collector.
Outbound W3C context propagation is separately opt-in through
`BAGO_OTEL_PROPAGATE_CONTEXT=1`, because it shares a correlation ID with the
request destination. OpenTelemetry is disabled by default and cannot change
Gateway authorization or adapter behavior. The demo verifies this one
server-policy read path; it does not establish instrumentation coverage for
every BAGO route or production runtime.

## Evidence boundary

The source lab has historical L15 evidence, but this demo's result is only
established by a fresh run. The launcher checks the live run and Jaeger query;
it does not update the sibling lab's canonical evidence or state. A passing
result validates this local E2E projection only. It says nothing about BAGO's
production runtime instrumentation, remote telemetry, retention, cloud
services or authorization enforcement.
