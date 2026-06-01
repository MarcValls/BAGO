# Sync Protocol

## Objetivo

Mantener el knowledge local compatible con el repositorio remoto de GitHub.

## Contrato

- `README.md` y `manifest.json` definen el índice.
- `topics/` contiene la memoria canónica.
- `examples/` contiene casos reproducibles.
- `schemas/` valida la forma.
- `assets/` visualiza el contenido.

## Regla de sincronización

Sincronizar por ruta y por contrato. No por carpetas improvisadas.



---

# CONTENIDO FUSIONADO DESDE RAÍZ (sync_protocol.md)


# BAGO — Protocolo de Sincronización

> Aprendido: 2026-06
> Contexto: sesión de desarrollo del BAGO Launcher

---

## Regla fundamental

**Cuando hay dispositivo BAGO disponible (`/Volumes/bago_core/`), cualquier cambio
en el repo se sincroniza TAMBIÉN al pendrive — siempre juntos, nunca por separado.**

```
cambio → ~/BAGO/ → git push → /Volumes/bago_core/  (los tres, siempre)
```

---

## Procedimiento estándar de sync

```bash
# 1. Verificar pendrive montado
if [ -d "/Volumes/bago_core" ]; then
  PENDRIVE_OK=true
else
  PENDRIVE_OK=false
fi

# 2. Commit + push a GitHub
cd ~/BAGO
git add -A
git commit -m "descripcion"
git push origin main

# 3. Si pendrive disponible → sync
if $PENDRIVE_OK; then
  rsync -av --exclude='.git' ~/BAGO/ /Volumes/bago_core/
  echo "✅ Pendrive sincronizado"
fi
```

---

## Directorios que siempre se sincronizan

| Carpeta | ~/BAGO/ | /Volumes/bago_core/ |
|---------|---------|---------------------|
| `.bago/` | ✅ | ✅ |
| `docs/` | ✅ | ✅ |
| `launcher/` | ✅ | ✅ (origen) |
| `tools/` | ✅ | ✅ |

---

## Regla de Terminal/procesos (aprendida misma sesión)

Antes de abrir una ventana Terminal o iniciar un proceso:
1. Comprobar si ya hay una ventana/proceso con ese ID abierto
2. Si existe → traer al frente / reutilizar
3. Si no existe → crear nueva

**Nunca abrir duplicados sin verificar.**

