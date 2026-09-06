# BAGO 4.10.0

Consolidación del kernel de siete puntos. Tag `v4.10.0` sobre `ad149f81` (merge de #206 en `main`).

## Cambios principales

- **Frontera kernel/extensión (AC3)**: contrato versionado `bago.kernel-boundary.v1.json` con test de enforcement; el backend conserva la autoridad sobre sesión, canon, ejecución y evidencia.
- **Capability API v1 (AC5)**: acuerdo backend/frontend sobre permisos (incluida `network`), puertas de confianza y confirmación, dry-run vía `/inspect` y receipts persistidos.
- **Identidad, capacidades y política de modelos (AC6)**: separadas con procedencia explícita; los modelos desconocidos no reciben capacidades fabricadas y el contrato incorrecto falla cerrado. RL permanece `can_execute=false`.
- **Consolidación de imports (AC4)**: el slice de providers vive en `bago_core.providers` con imports de paquete y sin mutación de `sys.path`; las facades preservan los entrypoints y el inventario de migración restante es verificable mecánicamente.
- **Proyecciones de verdad generadas (AC7)**: rutas de API, inventario de migración y versiones se regeneran desde sus autoridades y CI detecta la deriva.
- **Cadena de release (AC2, parcial)**: pipeline Authenticode que falla cerrado, preflight de firma de solo lectura y E2E real del instalador ejecutado en CI sobre el tag.

## Artefactos

| Archivo | SHA-256 |
|---|---|
| `bago-4.10.0-setup.exe` | `827771872EFFB5FD4908A55C461F7D96E38283E464C6D03630C17DC9BA50983A` |
| `bago-4.10.0-distribution.zip` | `C3D485DD6D9709ECE7777E53F3A684D57FA6DE4D54CCAB33BEAEAD669961877E` |

Cada artefacto lleva su sidecar `.sha256`. Verificación:

```powershell
(Get-FileHash bago-4.10.0-setup.exe -Algorithm SHA256).Hash
```

## Estado de firma

**Estos artefactos NO están firmados con Authenticode.** Windows SmartScreen mostrará una advertencia de editor desconocido al ejecutarlos.

La firma pública está bloqueada: no existe una identidad de firma autorizada ni el entorno protegido `release-signing`. El pipeline de firma falla cerrado por diseño y no se ha eludido. Para publicar artefactos firmados hay que configurar la identidad de firma y ejecutar el workflow de release protegido.

Verifica siempre los SHA-256 publicados antes de instalar.

## Evidencia de verificación

Sobre el contenido exacto de este tag (árbol idéntico a `f8020b32`):

- Canonical CI en el tag: `Validate source`, `Packaged Electron smoke` y `Real installer E2E` en verde.
- E2E real del instalador en CI: construcción, instalación, verificación de identidad y desinstalación.
- Verificación local: suite backend completa, E2E de instalador (instalar → identidad ligada al commit → backend sano → desinstalación limpia) y gate Authenticode confirmando `NotSigned`.

## Instalación

1. Descarga `bago-4.10.0-setup.exe`.
2. Verifica el SHA-256 contra el valor publicado.
3. Ejecuta el instalador (acepta la advertencia de SmartScreen; los binarios no están firmados).
