## BAGO v4.8.2

Release estable centrada en **reproducibilidad**, **trazabilidad** y **robustez del instalador**.

### Cambios clave

- Instalador NSIS **fail-closed**: aborta ante cualquier paso crítico fallido.
- Instalación fijada a referencia inmutable (4.8.2) en lugar de main mutable.
- Verificación final de BAGO.exe antes de registrar instalación y accesos directos.
- Endurecimiento Electron: lock de instancia única + espera activa de backend /health.
- CI canónica con validación completa (alidate) para el corte de release.

### Artefactos

| Archivo | Tamaño (bytes) | SHA-256 |
|---|---:|---|
| $f | 79571 | $sha |
| $f | 214569936 | $sha |
| $f | 178546 | $sha |
| $f | 13097 | $sha |
| $f | 2774 | $sha |

### Instalación recomendada (Windows)

1. Descarga y ejecuta ago-4.8.2-setup.exe.
2. Abre BAGO desde el acceso directo de Escritorio o Menú Inicio.
3. Verifica integridad comparando checksums .sha256.

### Notas de trazabilidad

- Tag objetivo: 4.8.2
- Instalación por usuario: %LOCALAPPDATA%\\BAGO
- Registro de instalación: HKCU\\Software\\BAGO (InstallPath, InstallRef)