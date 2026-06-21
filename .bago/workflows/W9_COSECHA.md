# W9 · Cosecha Contextual

## id
`w9_cosecha`

**ID:** `w9_cosecha`  
**Versión:** 1.0  
**Creado:** 2026-04-18  
**Origen:** ESCENARIO-003 — conclusiones de E001 + E002  
**Tiempo estimado:** ≤ 5 minutos  

---

## 1. Para qué sirve

W9 captura el valor generado durante **exploración libre** o trabajo sin estructura (modo `.bago/off`).

El problema que resuelve:

> El modo libre genera pensamiento útil, pero si no se formaliza, se pierde.  
> W9 actúa *después* de que el pensamiento madura, no *durante*.

W9 **no interrumpe** el flujo creativo. Solo se activa cuando hay señales de que el contexto está listo.

---

## 2. Cuándo activar W9

Activar W9 cuando el detector lo sugiera **o** cuando tú percibas:

- Tomaste una decisión relevante durante la exploración
- Descartaste al menos una opción con una razón
- Tienes claro el siguiente paso concreto

No activar W9 si:
- La exploración está a medias y el pensamiento no ha concluido
- No hay nada que decidir ni descartar aún

**Disparador automático:**

```bash
python3 .bago/tools/context_detector.py
# Si dice HARVEST → ejecutar W9
```

---

## 3. Protocolo — 3 preguntas, ≤5 minutos

```bash
python3 .bago/tools/cosecha.py
```

El script hace exactamente 3 preguntas:

| # | Pregunta | Captura |
|---|----------|---------|
| 1 | ¿Qué decidiste en esta exploración? | `decisions[0]` |
| 2 | ¿Qué descartaste y por qué? | `decisions[1]` |
| 3 | ¿Cuál es el próximo paso concreto? | `next_step` |

Con esas 3 respuestas genera automáticamente:

- 1 sesión cerrada (`task_type: "harvest"`, `status: "closed"`)
- 1 `CHG` con los ficheros modificados detectados
- 1 `EVD` con las 3 respuestas como `details`
- `global_state.json` actualizado

---

## 4. Después de la cosecha

```bash
# Regenerar TREE+CHECKSUMS
cd /ruta/a/tu/proyecto
python3 -c "
from pathlib import Path; import hashlib
root = Path('.bago')
entries = sorted(str(p.relative_to(root))+('/' if p.is_dir() else '') for p in root.rglob('*'))
(root/'TREE.txt').write_text('\n'.join(entries)+'\n')
lines = []
for p in sorted(root.rglob('*')):
    if p.is_file() and p.name != 'CHECKSUMS.sha256':
        lines.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}')
(root/'CHECKSUMS.sha256').write_text('\n'.join(lines)+'\n')
"
python3 .bago/tools/validate_pack.py
```

---

## 5. Diferencias con otros workflows

| Aspecto | W7 | W8 | W9 |
|---------|----|----|-----|
| Cuándo | Objetivo concreto conocido | Exploración sin objetivo | Después de exploración libre |
| Preflight | Completo | Mínimo | Ninguno (retroactivo) |
| Duración | Variable | Variable | ≤5 min |
| Genera sesión | Sí | Sí | Sí (`task_type: harvest`) |
| Interrumpe flujo | Sí (al inicio) | Mínimo | No (siempre a posteriori) |
| Requiere detector | No | No | Recomendado |

---

## 6. Reglas

- **Nunca** activar W9 en medio de una exploración activa
- **Siempre** incluir al menos 1 decisión y 1 descarte
- Si no hay descarte real, escribir: *"No se descartó ninguna opción explícitamente"*
- Máximo 1 cosecha por bloque de exploración (no fraccionar)
- `role_auditor` es el único rol necesario — no añadir más

---

## 7. Ejemplo de sesión harvest

```json
{
  "session_id": "SES-HARVEST-2026-04-18-001",
  "task_type": "harvest",
  "selected_workflow": "w9_cosecha",
  "roles_activated": ["role_auditor"],
  "status": "closed",
  "decisions": [
    "DECISIÓN: usar disparador semántico en lugar de temporal porque el tiempo es un proxy malo del estado cognitivo",
    "DESCARTE: disparador cada 30 minutos — interrumpe cuando el pensamiento está a medias"
  ],
  "next_step": "Implementar context_detector.py con señales técnicas + cognitivas",
  "summary": "Harvest W9. Decisión: disparador semántico. Próximo: context_detector.py."
}
```

---

## 8. Relación con ESCENARIO-003

W9 es el mecanismo central del ESCENARIO-003.  
Las hipótesis a validar con W9:

- **H1:** disparador contextual > disparador temporal en captura de valor
- **H2:** 3 preguntas W9 ≈ decisiones formalizadas de sesión W7 completa  
- **H3:** W9 no penaliza el flujo creativo porque actúa a posteriori
