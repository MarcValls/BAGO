# User Authorization Provenance Boundary v1

Estado: IMPLEMENTED_SLICE · CRIT_READY

## Propósito

Separar una afirmación de autorización de una autorización atribuible a una
interacción directa del usuario.

La ruta materializada en esta versión es Capability Packages HTTP.

Cadena normativa:

`requested operation`
→ `AuthorizationChallenge`
→ `direct user decision`
→ `UserAuthorizationProof`
→ `AuthorizationDecision`
→ `one-time Permit`
→ `ExecutionGateway`
→ `material execution`
→ `receipt`

## Invariantes

1. `CLIENT_CONFIRMED_BOOL != USER_AUTHORIZATION`.
2. `CLIENT_PERMISSION_LIST != AUTHORITY`.
3. `AGENT_ASSERTED_AUTHORIZATION != USER_AUTHORIZATION`.
4. Un Permit está ligado al fingerprint exacto de capability, inputs,
   permissions y session.
5. Modificar la operación después de autorizar invalida el Permit.
6. Un Permit se consume antes de la ejecución material y no admite replay.
7. El token del Permit no se persiste; solo se conserva su SHA-256.
8. La emisión de Permit por HTTP exige un canal interactivo admitido.
9. Fallos de origen, sesión, fingerprint, expiración o replay cierran en DENY.
10. El bridge no debe arrancar con auto-aprobación de tools.

## Implementación

- `backend/.bago/core/authorization_boundary.py`
  - `AuthorizationOperation`
  - `UserAuthorizationProof`
  - `AuthorizationDecision`
  - `Permit`
  - `AuthorizationBoundary`
  - `ExecutionGateway`
- `backend/.bago/api/handlers_capability_packages.py`
  - flujo challenge / approve / execute sobre el mismo endpoint.
  - ignora `confirmed` y `approved_permissions` recibidos del cliente como
    fuente de autoridad.
- `frontend/src/modules/capability-anatomy/ExternalCapabilitiesPanel.tsx`
  - el click explícito del usuario ejecuta challenge → approve → permit →
    execute.
- `backend/.bago/api/bridge.py`
  - arranca la política de tools en `ask`, no `always`.

## Alcance de seguridad actual

Esta versión prueba procedencia desde una superficie interactiva BAGO ligada a
la sesión del bridge. No prueba todavía identidad humana mediante WebAuthn,
Windows Hello, firma de dispositivo u otro autenticador fuerte.

Por tanto:

`INTERACTIVE_ORIGIN_VERIFIED = YES`

`STRONG_HUMAN_IDENTITY_VERIFIED = NO`

Un cliente que posea el token del bridge y pueda falsificar arbitrariamente el
canal HTTP queda fuera del threat model de este primer corte. El siguiente
endurecimiento debe separar criptográficamente el canal de decisión humana de
los canales disponibles para agentes.

## Migración pendiente a frontera única

Todavía existen rutas materiales fuera de este gateway. Deben migrarse, como
mínimo:

- tool calls del LLM;
- schedules y delegaciones persistentes;
- `/files/write`;
- ejecución de plans/jobs;
- comandos con efecto;
- operaciones Git/GitHub mutantes;
- release/update/apply;
- cualquier connector con write/delete/execute.

Hasta completar esa migración el estado global es:

`AUTHORIZATION_BOUNDARY = PARTIAL_BINDING`

No debe declararse `UNIQUE_EXECUTION_BOUNDARY`.
