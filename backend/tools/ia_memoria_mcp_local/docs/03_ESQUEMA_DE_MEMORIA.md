# Esquema de memoria

## Clases

- `MEM_CONFIRMED`: hecho o decisión confirmada.
- `MEM_INFERRED`: inferencia no confirmada.
- `MEM_TEMP`: dato de sesión.
- `MEM_CONFLICT`: incompatibilidad pendiente.
- `MEM_DEPRECATED`: información sustituida.
- `MEM_EVENT`: acción, fallo, verificación o cierre.

## Campos

`memory_id`, `project_id`, `scope`, `memory_class`, `category`, `statement`, `source_reference`, `authority_level`, `confidence`, `status`, fechas, relaciones y `file_path`.

## Estados

`proposed`, `active`, `pending`, `superseded`, `deprecated`, `rejected`.
