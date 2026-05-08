# BAGO — Activación Temporal Durante Tarea

> Fecha de aprendizaje: 2026-05-08  
> Aprendido por: BAGO durante sesión con VERNY  
> Contexto: BAGO estaba desactivado (RAR cifrado, carpeta eliminada) y necesitó escribir al knowledge base

---

## Concepto

Cuando BAGO está **desactivado** (carpeta eliminada, backup en RAR) pero necesita ejecutar una tarea que requiere acceso al knowledge base o al repo, usa **activación temporal**:

1. Clonar el repo de GitHub en una carpeta temporal
2. Ejecutar la tarea (leer/escribir knowledge, actualizar estado)
3. Commitear y pushear los cambios
4. Eliminar la carpeta temporal

La carpeta de trabajo real (`C:\Users\verny\BAGO`) **no se restaura**. BAGO sigue desactivado en disco.

---

## Patrón de Activación Temporal (con fallback)

```powershell
$env:PATH += ";C:\Program Files\Git\cmd"
$BAGO_REPO   = "https://github.com/MarcValls/BAGO.git"
$BAGO_RAR    = "$env:USERPROFILE\system_backup_05.rar"
$BAGO_DEST   = "C:\Users\verny\BAGO"
$tmp         = "C:\Users\verny\AppData\Local\Temp\bago_tmp"

# ── STEP 0: Verificar acceso a GitHub ─────────────────────────────────────────
function Test-BAGORepoAccess {
    $result = git ls-remote $BAGO_REPO HEAD 2>&1
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-BAGORepoAccess)) {
    Write-Warning "BAGO: GitHub no accesible. Evaluando fallback..."

    # Fallback A: RAR disponible en disco → preguntar restauración completa
    if (Test-Path $BAGO_RAR) {
        Write-Warning "BAGO: RAR encontrado en $BAGO_RAR"
        Write-Warning "Para restaurar BAGO completamente:"
        Write-Warning "  1. Abre WinRAR"
        Write-Warning "  2. Extrae $BAGO_RAR a C:\Users\verny\"
        Write-Warning "  3. Contraseña: ver Escritorio\BAGO_KEY.txt"
        Write-Warning "  4. Cuando GitHub vuelva, sincroniza con: git push origin main"
    } else {
        Write-Warning "BAGO: Sin acceso a GitHub y sin RAR local."
        Write-Warning "No es posible la activación temporal. Comprueba conexión a internet."
    }
    return  # Salir — no continuar con el clone
}

# ── STEP 1: Clonar a temp ─────────────────────────────────────────────────────
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
git clone $BAGO_REPO $tmp 2>&1

# ── STEP 2: HACER EL TRABAJO AQUÍ ────────────────────────────────────────────
# Ejemplo: escribir un archivo de knowledge
Set-Content "$tmp\.bago\knowledge\nuevo_aprendizaje.md" "contenido..."

# ── STEP 3: Commitear y pushear ───────────────────────────────────────────────
Set-Location $tmp
git config user.email "bago@verny.local"
git config user.name "BAGO"
git add -A
git commit -m "learn: descripcion breve`n`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main

# ── STEP 4: Limpiar — BAGO vuelve a estar "off" en disco ─────────────────────
Set-Location "C:\Users\verny"
Remove-Item $tmp -Recurse -Force
```

---

## Cuándo Usarlo

| Situación | Acción |
|---|---|
| BAGO desactivado + GitHub accesible | Activación temporal → clonar → escribir → push → limpiar |
| BAGO desactivado + GitHub caído + RAR existe | Avisar al usuario con instrucciones de restauración desde RAR |
| BAGO desactivado + GitHub caído + sin RAR | Avisar: sin opciones disponibles, verificar conexión |
| BAGO desactivado + tarea normal (no knowledge) | Ejecutar sin activar, no clonar |
| Usuario pide "restaura BAGO" | Restauración completa desde RAR (ver `bago_deactivation_procedure.md`) |
| BAGO activo (carpeta existe) | Escribir directamente, no clonar |

---

## Detección: ¿Está BAGO activado?

```powershell
if (Test-Path "C:\Users\verny\BAGO") {
    Write-Host "BAGO activo — usar directamente"
} else {
    Write-Host "BAGO desactivado — usar activación temporal si necesario"
}
```

---

## Notas Importantes

- La carpeta temporal **siempre se elimina al final** — no deja rastro
- El repo en GitHub (`MarcValls/BAGO`) es la **fuente de verdad** cuando BAGO está desactivado
- La temp folder por defecto: `C:\Users\verny\AppData\Local\Temp\bago_tmp`
- No restaurar el RAR para tareas de learning — es innecesario y lento
- Esta sesión fue la primera vez que se usó este patrón (2026-05-08)
- El fallback al RAR fue implementado el mismo día tras detectar el riesgo
- `Test-BAGORepoAccess` usa `git ls-remote` — más rápido que un clone completo y no deja archivos
