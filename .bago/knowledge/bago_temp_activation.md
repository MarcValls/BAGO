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

## Patrón de Activación Temporal

```powershell
$env:PATH += ";C:\Program Files\Git\cmd"
$tmp = "C:\Users\verny\AppData\Local\Temp\bago_tmp"

# 1. Clonar a temp
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
git clone https://github.com/MarcValls/BAGO.git $tmp 2>&1

# 2. --- HACER EL TRABAJO AQUÍ ---
# Ejemplo: escribir un archivo de knowledge
Set-Content "$tmp\.bago\knowledge\nuevo_aprendizaje.md" "contenido..."

# 3. Commitear y pushear
Set-Location $tmp
git config user.email "bago@verny.local"
git config user.name "BAGO"
git add -A
git commit -m "learn: descripcion breve`n`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main

# 4. Limpiar — BAGO vuelve a estar "off" en disco
Set-Location "C:\Users\verny"
Remove-Item $tmp -Recurse -Force
```

---

## Cuándo Usarlo

| Situación | Acción |
|---|---|
| BAGO desactivado + necesita aprender algo | Activación temporal → clonar → escribir → push → limpiar |
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
