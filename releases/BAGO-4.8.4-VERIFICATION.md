# BAGO 4.8.4 - Verificación de Integridad

## ℹ️ Información Importante

Los binarios de BAGO 4.8.4 han sido compilados desde el commit exacto del tag `v4.8.4` (commit: e17b656).

### Archivos Compilados (Correctos)

| Archivo | SHA256 Checksum | Tamaño | Compilado desde |
|---------|-----------------|--------|-----------------|
| `bago-4.8.4-distribution.zip` | `4C79F5227EC3E111D36F5533E1AC10CA07FE1C13FFF8DD31D5A4C8E40BC57B96` | 240 MB | v4.8.4 tag (e17b656) |
| `bago-4.8.4-setup.exe` | `A36544A402EB954C0E53AA60DBA4C89ED85015E4B1D67D0B5848AF52B2C427B3` | 198 MB | v4.8.4 tag (e17b656) |
| `BAGO.exe` (aplicación) | `A1C1ED7D7D5F65EF73D63B9C1E2B9D86893D6C16C365DCBC88B6CD99D1DBF22B` | 216 MB | v4.8.4 tag (e17b656) |

## ✅ Verificación de Descarga

Después de descargar cualquiera de los binarios, verifica su integridad:

### Windows (PowerShell)
```powershell
(Get-FileHash -Path "bago-4.8.4-setup.exe" -Algorithm SHA256).Hash
```

Debe coincidir con: `A36544A402EB954C0E53AA60DBA4C89ED85015E4B1D67D0B5848AF52B2C427B3`

### Linux/macOS (Terminal)
```bash
sha256sum bago-4.8.4-distribution.zip
```

Debe coincidir con: `4C79F5227EC3E111D36F5533E1AC10CA07FE1C13FFF8DD31D5A4C8E40BC57B96`

## 🔍 Detalles Técnicos

- **Tag de release**: `v4.8.4`
- **Commit**: `e17b656` (fix: close Codex workspace turns reliably)
- **Rama de distribución**: `agent/ux-workspace-release-closure`
- **Compilador NSIS**: MakeSIS 3.x
- **Compresión**: LZMA
- **Electron**: 42.3.0

## 📋 Opciones de Instalación

1. **Setup.exe** (Recomendado para usuarios)
   - Instalación automática
   - Creación de accesos directos
   - Desinstalador integrado
   - Tamaño: 198 MB

2. **Distribution ZIP** (Para instalaciones manuales)
   - Extrae backend + frontend
   - Compatible con PowerShell script
   - Tamaño: 240 MB

3. **BAGO.exe** (Ejecutable portátil)
   - Aplicación portable sin instalación
   - Requiere Python backend separado
   - Tamaño: 216 MB

## ⚠️ Historial de Compilaciones

| Versión | Estado | Nota |
|---------|--------|------|
| 4.8.4 (Actual) | ✅ Correcto | Compilado desde tag v4.8.4 exacto |
| 4.8.3 | ✅ Estable | Compilado desde tag v4.8.3 |
| 4.8.2 | ✅ Estable | Compilado desde tag v4.8.2 |

---

**Última actualización**: 2026-08-10 05:07 UTC+2
**Verificado por**: Copilot Release Agent
