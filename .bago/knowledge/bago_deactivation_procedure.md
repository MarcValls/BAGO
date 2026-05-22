# BAGO — Procedimiento de Desactivación

> Fecha de aprendizaje: 2026-05-10
> Estado: implementado en `bago deactivate`

---

## Objetivo

Cuando el usuario pide **desactivar BAGO**, el flujo actual es:

1. Crear un archivo comprimido con el árbol operativo de BAGO.
2. Guardarlo en `.bago/backups/`.
3. Aplicar atributos de oculto + sistema en Windows.

El proceso es **no destructivo**: no elimina la carpeta fuente.

---

## Comando

```powershell
bago deactivate
```

Opciones:

```powershell
bago deactivate --tag cierre_2026
bago deactivate --no-hide
```

---

## Qué se incluye

El archivo de desactivación agrupa estos elementos si existen:

- `.bago/`
- `launcher/`
- `bago_core/`
- `bago`
- `bago.cmd`
- `AGENTS.md`
- `README.md`
- `INSTALL.md`
- `QUICKSTART.md`
- `QUICK_START.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- `LICENSE`
- `Makefile`
- `pyproject.toml`
- `bago-framework.code-workspace`

Se excluyen explícitamente los directorios pesados de estado y caché:

- `.bago/backups/`
- `.bago/.models/`

El archivo de salida se llama:

```powershell
.bago\backups\bago_deactivated_<timestamp>.zip
```

---

## Comportamiento en Windows

Si `--no-hide` no se usa, el archivo comprimido recibe:

```powershell
attrib +h +s <archivo>
```

Esto lo deja oculto y marcado como archivo de sistema.

---

## Restauración manual

```powershell
Expand-Archive -Path .bago\backups\bago_deactivated_<timestamp>.zip -DestinationPath <destino>
```

Si se usa `--no-hide`, el archivo queda visible y se puede tratar como un ZIP normal.

---

## Nota de implementación

- El flujo está registrado en `backup_manager.py` como subcomando `deactivate`.
- La ruta queda integrada en `tool_registry.py` para poder invocarse desde `bago`.
- No se borra el árbol original.
- No se usa cifrado por contraseña en la implementación actual.
