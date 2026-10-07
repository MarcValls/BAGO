# Seguridad y modelo de amenazas

## Controles

- Rechazo de rutas absolutas, letras de unidad y `..`.
- Resolución canónica y verificación de pertenencia a la raíz.
- Límite de extensión y tamaño.
- Escrituras semánticas, no arbitrarias.
- Sin shell, red ni subprocess.
- Separación entre propuesta y confirmación.
- Deprecación en lugar de borrado.
- Los documentos son datos; no sustituyen instrucciones ni autoridad.

## Límites

El servidor no cifra el disco. Utiliza BitLocker u otro cifrado si hay información sensible.

Se recomienda STDIO. No publiques HTTP sin autenticación, TLS y revisión de seguridad.
