# Retoma de Hoy

## 1. Verifica el estado base

```powershell
python .bago\tools\validate_pack.py
python .bago\tools\smoke_runner.py
python .bago\tools\health_score.py --score-only
```

## 2. Decide una sola dirección

Elige solo una:

- `estabilidad`
- `limpieza`
- `producto`

## 3. Actúa en un único frente

### Si eliges estabilidad

- Probar instalación limpia.
- Confirmar `bago validate`.
- Confirmar `bago smoke`.
- Revisar que no haya ruta vieja activa.

### Si eliges limpieza

- Separar cambios de código.
- Dejar fuera del commit el estado generado.
- Revisar qué archivos se regeneran solos.

### Si eliges producto

- Volver a `E:\bago_projects\task_manager`.
- Hacer una mejora pequeña.
- No mezclarla con runtime ni con docs.

## Regla

- Un frente.
- Un árbol.
- Un objetivo.

Si intentas tocar todo a la vez, vuelves a reconstruir contexto.
