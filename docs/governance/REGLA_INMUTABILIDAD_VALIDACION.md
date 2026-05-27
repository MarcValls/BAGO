# Regla de inmutabilidad de validacion

La validacion canónica no debe:

- asumir éxito sin comprobar el estado real
- escribir residuos permanentes durante una comprobacion
- ocultar errores de coherencia

Si falla un gate, se informa el fallo exacto.
