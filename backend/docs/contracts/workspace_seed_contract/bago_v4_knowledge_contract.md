# Contrato de conocimiento recuperable de BAGO v4

## Alcance

Este contrato regula cómo una conversación o mejora pasa a formar parte del conocimiento reutilizable de BAGO v4.

## Unidad mínima válida

Una entrada de conocimiento útil debe tener:

- contenido textual suficientemente específico para recuperarse después,
- `source_session` asociado,
- fecha de creación persistida por `KnowledgeBase`,
- una evidencia o comando que permita reproducir el contexto en el que se añadió.

## Reglas

1. El conocimiento no sustituye la sesión: la complementa.
2. Una memoria válida debe poder recuperarse con `/memory search`.
3. Una contribución comunitaria no cuenta como conocimiento integrado hasta que existe un bundle de evidencia asociado.
4. El contenido debe describir una ayuda reutilizable, no solo una intención abstracta.

## Flujo contractual

```text
Necesidad del usuario
-> respuesta o acción útil
-> memoria persistente
-> bundle de evidencia
-> reutilización por otro usuario o tarea
```

## Comandos mínimos

```powershell
/memory add <texto>
/memory search <consulta>
/memory list
```

## Validación

El bundle generado por:

```powershell
python bago_core\cli.py evidence --mode simulated --objective community-knowledge --output docs\evidence\ui_shell_current --overwrite
```

debe contener `knowledge\recent_memories.json` con la memoria añadida durante la ejecución.
