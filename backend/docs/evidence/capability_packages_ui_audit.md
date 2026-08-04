# Auditoría UI · Capability Packages

- Superficie canónica: `frontend/src/modules/capability-anatomy`, accesible desde `Grafo > Capacidades`.
- Autoridad: backend local; la UI no carga componentes ni JavaScript del paquete.
- P0 cerrado: importar ZIP, validar manifest, activar, configurar, ejecutar y emitir receipt persistente.
- P1 cerrado: estados vacío/cargando/error/éxito, confirmación de confianza y confirmación separada de ejecución.
- Contrato: `bago.capability/v1`, UI declarativa desde schemas JSON y runner Python sin shell.
- Límites: ZIP 600 KB, 64 entradas, 2 MB descomprimido, timeout máximo 900 s y salida máxima 64 KB.
- Riesgo visible: un runner Python confiado puede ejecutar código local; los permisos son aprobación explícita, no un sandbox del sistema operativo.
