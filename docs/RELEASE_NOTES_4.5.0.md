# BAGO 4.5.0 - Manager v1 + Landing Fullscreen

### Novedades
- **Manager v1**: Nueva pestana "Estado del Sistema" (Sistema) con:
  - Monitor del supervisor BAGO (iniciar / detener / reiniciar)
  - Limpieza de conexiones zombie (TIME_WAIT / CloseWait / FinWait2)
  - Panel de salud del Manager (probes de 5 servicios criticos)
- **Landing page**: hero ocupa toda la pantalla en cualquier dispositivo (flex layout centrado)
- **Distribucion**: descarga directa del Manager Installer desde GitHub Releases

### Assets
- BAGO-Installation-Manager-4.5.0-win-x64.exe - Instalador del Manager (Electron)
- bago-v4.5.0.zip - Bundle de fuentes v4
- bago-v4.5.0.zip.sha256 - Checksum SHA256

### Instalacion rapida
1. Descarga el .exe del Manager
2. Ejecuta el instalador
3. El Manager detecta si BAGO esta instalado y ofrece instalar / reparar / actualizar
4. Accede a la pestana "Sistema" para gestionar el supervisor y limpiar conexiones zombie

### Notas
- Este release usa solo caracteres ASCII para evitar problemas de renderizado.
- El instalador remoto queda anclado al tag v4.5.0.
