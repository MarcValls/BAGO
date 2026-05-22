# PLANTILLA · EVALUACIÓN BRUTAL DE BAGO

## 0. Meta de esta plantilla

Esta plantilla existe para responder una sola pregunta:

**¿BAGO mejora de verdad el trabajo técnico complejo o solo lo ordena con más ceremonia?**

No evalúa si el sistema “suena bien”.
Evalúa si produce ventajas medibles en repositorios reales.

---

## 1. Identificación de la evaluación

- **Evaluación ID:**
- **Fecha:**
- **Evaluador:**
- **Repositorio / ámbito:**
- **Rama:**
- **Commit o snapshot base:**
- **Sesión BAGO asociada:**
- **Versión del pack BAGO:**
- **Objetivo de la evaluación:**
- **Tipo de evaluación:**
  - [ ] benchmark vs baseline
  - [ ] cold start
  - [ ] drift test
  - [ ] cambio sensible
  - [ ] overhead
  - [ ] handoff / orquestación
  - [ ] auditoría semanal
  - [ ] otra

---

## 2. Hipótesis a probar

### Hipótesis principal

- **Hipótesis:**
- **Qué mejora debería aportar BAGO:**
- **Cómo se medirá:**

### Hipótesis secundarias

- **H2:**
- **H3:**
- **H4:**

---

## 3. Contexto operativo de partida

### Estado del repo

- **Stack detectado:**
- **Módulos principales afectados:**
- **Complejidad estimada:** baja / media / alta
- **Cambios sin commit al arrancar:**
- **Riesgos abiertos iniciales:**
- **Restricciones activas:**
- **Decisiones congeladas vigentes:**

### Estado BAGO al inicio

- **Objetivo actual:**
- **Modo predominante:**
- **Fase actual:**
- **Roles activos al inicio:**
- **Siguiente paso registrado:**

### Calidad del arranque

- [ ] Se usó `pnpm bago:start`
- [ ] Se verificó la carga canónica
- [ ] Se contrastó el estado BAGO con el repo real
- [ ] Se registraron divergencias si existían
- [ ] No se empezó a ejecutar antes del bootstrap

---

## 4. Baseline de comparación

> Rellena esto aunque te parezca obvio. Si no hay baseline, no hay evaluación dura.

### Opción A · Baseline sin BAGO

- **Cómo se haría la tarea sin BAGO:**
- **Herramientas usadas:**
- **Tiempo estimado:**
- **Riesgos del baseline:**
- **Qué no quedaría trazado:**

### Opción B · Baseline mínimo compatible

- **Checklist mínimo alternativo:**
- **Estado simple alternativo:**
- **Scripts simples equivalentes:**
- **Por qué este baseline es justo:**

---

## 5. Definición de la tarea bajo prueba

- **Nombre de la tarea:**
- **Descripción concreta:**
- **Resultado esperado:**
- **Criterio mínimo de éxito:**
- **Criterio de fallo:**
- **Sensibilidad del cambio:**
  - [ ] no sensible
  - [ ] sensible
- **Si es sensible, por qué:**
- **Artefactos esperados:**
  - [ ] código
  - [ ] tests
  - [ ] documentación
  - [ ] estado actualizado
  - [ ] cambio estructural registrado
  - [ ] auditoría
  - [ ] reporte

---

## 6. Workflow evaluado

### Workflow principal usado

- [ ] W1 · Benchmark vs baseline
- [ ] W2 · Cold start real
- [ ] W3 · Drift test de iteraciones
- [ ] W4 · Cambio sensible
- [ ] W5 · Overhead
- [ ] W6 · Handoff / orquestación
- [ ] W7 · Auditoría semanal

### Resumen del workflow

- **Entrada:**
- **Secuencia ejecutada:**
- **Salida esperada:**
- **Duración prevista:**
- **Duración real:**

---

# W1 · BENCHMARK VS BASELINE

## 7. Ejecución del baseline

- **Hora de inicio:**
- **Hora fin primer resultado útil:**
- **Hora fin resultado aceptable:**
- **Errores detectados:**
- **Archivos tocados:**
- **Correcciones posteriores necesarias:**
- **Notas cualitativas:**

## 8. Ejecución con BAGO

- **Hora de inicio:**
- **Hora fin primer resultado útil:**
- **Hora fin resultado aceptable:**
- **Modo predominante real:**
- **Roles realmente activos:**
- **Cambios de fase durante la sesión:**
- **Errores detectados:**
- **Archivos tocados:**
- **Correcciones posteriores necesarias:**
- **Notas cualitativas:**

## 9. Comparativa W1

| Métrica                                 | Baseline | BAGO | Diferencia | Juicio |
| --------------------------------------- | -------: | ---: | ---------: | ------ |
| Tiempo a primer resultado útil          |          |      |            |        |
| Tiempo a resultado aceptable            |          |      |            |        |
| Nº de correcciones                      |          |      |            |        |
| Nº de archivos tocados innecesariamente |          |      |            |        |
| Retrabajo en iteración siguiente        |          |      |            |        |
| Claridad del siguiente paso             |          |      |            |        |
| Trazabilidad real                       |          |      |            |        |

### Veredicto W1

- **¿BAGO ganó?**
- **¿Dónde ganó de verdad?**
- **¿Dónde añadió peso sin compensar?**

---

# W2 · COLD START REAL

## 10. Datos del arranque

- **Se ejecutó `pnpm bago:start`:** sí / no
- **Precondiciones OK:** sí / no
- **Carga canónica OK:** sí / no
- **Se generó snapshot de sesión:** sí / no
- **Tiempo hasta resumen correcto del repo:**
- **Tiempo hasta objetivo útil:**
- **Tiempo hasta siguiente paso útil:**

## 11. Precisión del arranque

| Criterio                         | Resultado | Observación |
| -------------------------------- | --------- | ----------- |
| Stack detectado correctamente    |           |             |
| Propósito del repo bien inferido |           |             |
| Restricciones bien leídas        |           |             |
| Riesgos iniciales útiles         |           |             |
| Estado vivo consistente con repo |           |             |
| Roles iniciales bien elegidos    |           |             |

### Veredicto W2

- **¿Sirve BAGO para arrancar un repo real sin teatro?**
- **¿Qué parte del arranque sobró?**
- **¿Qué parte faltó?**

---

# W3 · DRIFT TEST DE ITERACIONES

## 12. Diseño del test

- **Número de iteraciones:**
- **Separación temporal entre iteraciones:**
- **Fuentes permitidas para retomar:**
  - [ ] `.bago/state/ESTADO_BAGO_ACTUAL.md`
  - [ ] snapshots de sesión
  - [ ] cambios registrados
  - [ ] artefactos producidos
- **Fuentes prohibidas:**
  - [ ] conversación completa previa
  - [ ] memoria informal del operador
  - [ ] reconstrucción manual extensa

## 13. Resultado por iteración

| Iteración | Objetivo entendido | Siguiente paso claro | Contradicciones detectadas | Contexto rehecho manualmente | Juicio |
| --------- | ------------------ | -------------------- | -------------------------- | ---------------------------- | ------ |
| 1         |                    |                      |                            |                              |        |
| 2         |                    |                      |                            |                              |        |
| 3         |                    |                      |                            |                              |        |

### Veredicto W3

- **¿BAGO conserva continuidad real o solo genera papeles?**
- **¿Dónde apareció deriva?**
- **¿Qué campo del estado falló más?**

---

# W4 · CAMBIO SENSIBLE

## 14. Naturaleza del cambio

- **Tipo de cambio sensible:**
  - [ ] arquitectura
  - [ ] contrato público
  - [ ] migración
  - [ ] seguridad
  - [ ] CI/CD
  - [ ] automatización transversal
  - [ ] otro
- **Motivo del cambio:**
- **Validación humana explícita obtenida:** sí / no
- **Registro de cambio estructural creado:** sí / no

## 15. Control del cambio

| Control                                | Sí/No | Observación |
| -------------------------------------- | ----- | ----------- |
| Se delimitó el alcance                 |       |             |
| Se explicó impacto y riesgo            |       |             |
| Se respetaron decisiones congeladas    |       |             |
| Se actualizó el estado vivo            |       |             |
| Se registró cambio en `state/cambios/` |       |             |
| Se dejó rollback comprensible          |       |             |

### Veredicto W4

- **¿BAGO previno el desastre o solo lo documentó después?**
- **¿La gobernanza fue útil o decorativa?**

---

# W5 · OVERHEAD

## 16. Ratio de sobrecarga

- **Tiempo de arranque y ceremonia:**
- **Tiempo de trabajo útil:**
- **Ratio overhead = ceremonia / trabajo útil:**

### Interpretación

- **< 0.15** → excelente
- **0.15 – 0.35** → aceptable
- **0.35 – 0.60** → pesado
- **> 0.60** → probablemente excesivo
- **> 1.00** → no debería usarse así para este tipo de tarea

## 17. Fuentes de fricción

- [ ] demasiada lectura inicial
- [ ] estado demasiado verboso
- [ ] roles innecesarios
- [ ] actualización de estado demasiado frecuente
- [ ] protocolos poco compactos
- [ ] mezcla entre arranque y ejecución
- [ ] otra

### Veredicto W5

- **¿Cuánta burocracia real metió BAGO?**
- **¿Dónde recortar sin romper el sistema?**

---

# W6 · HANDOFF / ORQUESTACIÓN

## 18. Diseño del handoff

- **Tarea original:**
- **Agente o rol de entrada:**
- **Agente o rol de destino:**
- **Motivo del handoff:**
- **Política aplicada:**
- **Riesgo de handoff:** bajo / medio / alto

## 19. Calidad del handoff

| Criterio                         | Sí/No | Observación |
| -------------------------------- | ----- | ----------- |
| El handoff estaba justificado    |       |             |
| El contexto llegó suficiente     |       |             |
| No hubo retrabajo innecesario    |       |             |
| El rol destino mejoró la calidad |       |             |
| Se mantuvo la trazabilidad       |       |             |

### Veredicto W6

- **¿El handoff reduce errores o solo desplaza el trabajo?**
- **¿Qué política de handoff funciona y cuál no?**

---

# W7 · AUDITORÍA SEMANAL

## 20. Resumen semanal

- **Semana:**
- **Repos evaluados:**
- **Sesiones BAGO evaluadas:**
- **Bloques de trabajo cerrados:**
- **Cambios estructurales registrados:**
- **Revisiones evolutivas abiertas:**
- **Auditorías técnicas corridas:**
  - [ ] `audit:weekly:run`
  - [ ] `audit:a11y`
  - [ ] `audit:perf`

## 21. Métricas semanales

| Métrica                                   | Valor | Semana anterior | Tendencia | Juicio |
| ----------------------------------------- | ----: | --------------: | --------- | ------ |
| Sesiones con estado actualizado           |       |                 |           |        |
| Sesiones con siguiente paso claro         |       |                 |           |        |
| Cambios sin rastro suficiente             |       |                 |           |        |
| Activaciones de más de 3 roles            |       |                 |           |        |
| Revisiones evolutivas justificadas        |       |                 |           |        |
| Retrabajos por deriva                     |       |                 |           |        |
| Incidencias por contradicción estado/repo |       |                 |           |        |
| Score a11y                                |       |                 |           |        |
| Score perf                                |       |                 |           |        |

### Veredicto W7

- **¿La semana fue más gobernable con BAGO?**
- **¿Qué señal empeoró?**
- **¿Qué señal mejora de forma consistente?**

---

## 22. Scorecard general

### Ponderaciones

- **Claridad operativa:** 20%
- **Continuidad real:** 20%
- **Contención de deriva:** 20%
- **Utilidad del output:** 25%
- **Coste del sistema:** 15%

### Puntuación

| Dimensión            | Nota /100 | Peso | Puntuación ponderada |
| -------------------- | --------: | ---: | -------------------: |
| Claridad operativa   |           | 0.20 |                      |
| Continuidad real     |           | 0.20 |                      |
| Contención de deriva |           | 0.20 |                      |
| Utilidad del output  |           | 0.25 |                      |
| Coste del sistema    |           | 0.15 |                      |

- **TOTAL:**

### Interpretación del total

- **85–100** → BAGO aporta valor claro y repetible
- **70–84** → útil, pero aún pesado o irregular
- **55–69** → prometedor, no suficientemente probado
- **<55** → sistema bonito, valor no demostrado

---

## 23. Fallos detectados sin maquillaje

### Fallos duros

- **F1:**
- **F2:**
- **F3:**

### Fallos blandos

- **FB1:**
- **FB2:**
- **FB3:**

### Fallos de diseño BAGO

- **Qué parte del sistema generó fricción inútil:**
- **Qué documento sobró:**
- **Qué regla faltó:**
- **Qué automatización faltó:**

---

## 24. Decisiones de mejora

### Conservar

- **Qué conservaría tal cual:**
- **Por qué:**

### Recortar

- **Qué recortaría:**
- **Por qué:**

### Endurecer

- **Qué volvería más estricto:**
- **Por qué:**

### Automatizar

- **Qué debería pasar a script o validación automática:**
- **Por qué:**

---

## 25. Próximo experimento

- **Próximo workflow a correr:**
- **Hipótesis del próximo experimento:**
- **Métrica principal:**
- **Criterio de éxito:**
- **Fecha prevista:**

---

## 26. Veredicto final

### Juicio corto

- **BAGO en este caso fue:**
  - [ ] claramente útil
  - [ ] útil con sobrecarga
  - [ ] neutro
  - [ ] más pesado que útil
  - [ ] no demostró valor

### Juicio sincero

- **Qué problema resolvió de verdad:**
- **Qué promesa no cumplió:**
- **Qué tendría que pasar para llamarlo indispensable:**

---

# ANEXO A · CHECKLIST RÁPIDO DE EVALUACIÓN

- [ ] hubo baseline o comparación justa
- [ ] el repo era real, no abstracto
- [ ] el arranque partió de `.bago/`
- [ ] se contrastó estado vs repo
- [ ] la tarea tenía criterio de éxito claro
- [ ] se midió tiempo útil, no solo sensación
- [ ] se midió retrabajo
- [ ] se midió deriva
- [ ] se midió sobrecarga
- [ ] se dejó veredicto duro, no decorativo

# ANEXO B · FRASES PROHIBIDAS EN LA EVALUACIÓN

No escribir:

- “parece útil”
- “da buena sensación”
- “me ayudó bastante”
- “se ve sólido”
- “ordenó mejor todo”

Sustituir por:

- “redujo X minutos”
- “evitó Y retrabajos”
- “bajó de N a M contradicciones”
- “el siguiente paso quedó listo sin reconstrucción”
- “añadió Z minutos de ceremonia”
