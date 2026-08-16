# Contratos frontend-backend

Usa `bago_contracts_auditor` y apóyate en `bago_code_mapper` cuando haga falta.

Construye la trazabilidad:
FRONTEND CALL -> ENDPOINT -> HANDLER -> RESULTADO -> TEST -> ESTADO.

Audita transporte, timeout, cancelación, retries, serialización, parsing, errores, tipos, GET/POST/PUT/DELETE,
streaming y compatibilidad de versiones.

Señala métodos obsoletos, endpoints sin consumidor, UI llamando rutas inexistentes, tipos duplicados
y respuestas asumidas sin validación.
