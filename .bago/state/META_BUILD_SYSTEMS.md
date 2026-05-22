# BAGO Build Multiplataforma — Aprendizaje Persistente
## Fecha: 2026-05-15
## Pipeline: Build universal (APK + Electron + Docker)

---

## 1. APK Android (TWA — Trusted Web Activity)

**Tecnica:** Bubblewrap CLI genera un proyecto Android que empaqueta la PWA en un Chrome Custom Tab sin UI de navegador.

**Ventajas:**
- APK nativo instalable
- Acceso a notificaciones push, icono en launcher
- Actualizaciones via web (sin update de APK)
- 90% codigo compartido con PWA

**Limitaciones:**
- Requiere conexion a internet (salvo service worker offline)
- No acceso a hardware avanzado (solo via web APIs)
- Firma requerida para Play Store

**Comando:**
```bash
python .bago/tools/bago_apk_builder.py \
  --url https://marcvalls.github.io/bago-music-saas/ \
  --name "BAGO Music" \
  --package dev.bago.music
```

**Requisitos:**
- Node.js, npm
- Bubblewrap CLI (`npm install -g @bubblewrap/cli`)
- JDK 17 (auto-install por bubblewrap)
- Android SDK (auto-install por bubblewrap)

---

## 2. App de Escritorio (Electron)

**Tecnica:** Electron = Chromium + Node.js empaquetados. La app carga la URL via `loadURL()`.

**Ventajas:**
- .exe nativo para Windows
- .dmg para macOS
- .AppImage para Linux
- Acceso a filesystem, notificaciones nativas
- Auto-updater integrado

**Limitaciones:**
- Tamaño ~150MB (incluye Chromium)
- RAM ~300MB por instancia
- No es sandboxed como navegador

**Comando:**
```bash
python .bago/tools/bago_electron_packager.py \
  --url https://marcvalls.github.io/bago-music-saas/ \
  --name "BAGO Music"
```

**Requisitos:**
- Node.js, npm
- electron-builder (auto-install por script)

---

## 3. Docker / Cloud

**Tecnica:** Backend FastAPI en contenedor, servido via uvicorn.

**Ventajas:**
- Deploy uniforme en cualquier cloud
- Escalable horizontalmente
- CI/CD friendly
- Free tiers disponibles (Render, Fly.io, Railway)

**Comando:**
```bash
docker-compose up --build
```

**Plataformas compatibles:**
- Render.com (free, 24/7 con cold start)
- Fly.io (free, 2 apps)
- Railway (free, 500h/mes)
- AWS/GCP/Azure (paid)

---

## 4. Checklist Universal de Build

Antes de cualquier build:
- [ ] PWA manifest valido (name, short_name, icons 192+512, start_url, display standalone)
- [ ] Service Worker registrado para offline
- [ ] API_BASE configurable via env var (no hardcode localhost)
- [ ] CORS configurado para dominio de produccion
- [ ] Iconos SVG/PNG en raiz (favicon, apple-touch-icon)
- [ ] Tokens/secrets en variables de entorno
- [ ] HTTPS obligatorio (para TWA y service worker)

---

## 5. Comparativa de Tecnologias

| Tecnologia | Tamaño | Offline | Push | Nativo | Coste |
|------------|--------|---------|------|--------|-------|
| PWA pura   | 0MB    | SW      | Web  | No     | Free  |
| TWA/APK    | 3MB    | SW      | Web  | Si     | Free  |
| Electron   | 150MB  | Cache   | OS   | Si     | Free  |
| Docker     | 200MB  | Si      | API  | No     | Free* |

---

## 6. Meta-pipeline Reutilizable

**Fases:**
1. **Validate** — checklist de build universal
2. **Scaffold** — generar proyecto contenedor (android/, electron/, docker/)
3. **Build** — ejecutar herramienta nativa (bubblewrap, electron-builder, docker)
4. **Sign** — firma de release (APK cert, Electron code-sign)
5. **Distribute** — subir a Play Store, GitHub Releases, Docker Hub

**Comando BAGO propuesto:**
```
BAGO build --target apk|electron|docker|all --url https://app.com --name "App"
```

**Proximas mejoras:**
- [ ] Capacitor (alternativa a Bubblewrap, acceso nativo a camara/GPS)
- [ ] Tauri (alternativa a Electron, Rust-based, mas ligero)
- [ ] Flutter Web (si se requiere UI nativa completa)
- [ ] Auto-CI en GitHub Actions para builds nocturnos
