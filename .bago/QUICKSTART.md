# BAGO QUICKSTART — v3.2-kernel

> Guía rápida de arranque. Para documentación completa: ver `QUICKSTART.md` en la raíz del repo.

---

## Instalación

```bash
git clone https://github.com/MarcValls/BAGO.git
cd BAGO
pip install -e .
```

## Verificación

```bash
bago validate   # GO manifest / GO state / GO pack
bago health     # score de salud (initializing en instalación nueva)
```

## Primera sesión

```bash
bago session open        # abre sesión con contexto del handoff anterior
bago status              # flujo activo + tarea pendiente
bago ideas               # ideas priorizadas para trabajar
```

## Cierre de sesión

```bash
bago session harvest     # cosecha artefactos (W9)
bago validate            # verifica integridad antes de commit
```

## Arranque del agente de IA

Añade esta instrucción al inicio de cualquier sesión con tu agente:

```
Lee .bago/AGENT_START.md antes de hacer nada. Luego procede.
```

## Workflows disponibles (W0–W10)

| Workflow | Cuándo |
|---|---|
| W0 · Sesión Libre | Exploración sin estructura |
| W1 · Cold Start | Primera vez en el repo |
| W2 · Implementación Controlada | Feature con tarea definida |
| W3 · Refactor Sensible | Cambios estructurales de riesgo |
| W4 · Debug Multicausa | Bug con varias causas posibles |
| W5 · Cierre y Continuidad | Handoff de sesión |
| W6 · Ideación Aplicada | Generación de ideas |
| W7 · Foco de Sesión | Objetivo único (uso diario recomendado) |
| W8 · Exploración | Investigación libre |
| W9 · Cosecha | Formalizar artefactos de sesión libre |
| W10 · Auditoría de Sinceridad | Detectar afirmaciones sin evidencia |

---

*BAGO v3.2-kernel · Ver `docs/GETTING_STARTED.md` para guía extendida.*

