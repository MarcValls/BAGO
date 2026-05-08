# Notas de Mejoras Generales

**Sesión libre · OFF R5 · Sin estructura**

Ideas generales para mejorar el pack:

- Podría haber un dashboard
- La documentación podría estar más organizada
- Los workflows son complicados
- Habría que simplificar el cierre de sesiones

Sin más detalles ni plan de implementación.

---

## Pendiente — Activación Temporal: Fallback si GitHub no disponible

**Detectado:** 2026-05-08 · Sesión con VERNY  
**Prioridad:** Media  
**Contexto:** `bago_temp_activation.md`

### Riesgo
Si GitHub cae o el repo pasa a privado sin credenciales configuradas en el PC,
`git clone` falla silenciosamente y BAGO no puede hacer la activación temporal.
El agente podría continuar como si todo estuviera bien sin avisar al usuario.

### Solución propuesta
Antes del clone, verificar accesibilidad y credenciales:

```powershell
function Test-BAGORepoAccess {
    $result = git ls-remote https://github.com/MarcValls/BAGO.git HEAD 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "BAGO: No se puede acceder al repo GitHub. Activación temporal cancelada."
        Write-Warning "Causas posibles: sin internet, repo privado sin token, GitHub caído."
        Write-Warning "Alternativa: restaurar desde RAR con contraseña en Escritorio\BAGO_KEY.txt"
        return $false
    }
    return $true
}
```

Integrar esta función al inicio del patrón de activación temporal antes de clonar.

### Estado
- [ ] Implementar `Test-BAGORepoAccess` en el patrón de activación temporal
- [ ] Actualizar `bago_temp_activation.md` con el bloque de verificación
- [ ] Considerar fallback: si GitHub inaccesible y RAR existe → preguntar si restaurar completo
