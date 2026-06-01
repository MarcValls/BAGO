# BAGO UI React

UI dual en React para BAGO:

- **Terminal**: shell/chat con comandos
- **Escritorio**: paneles visuales con el mismo control

Ambas vistas usan el mismo backend HTTP de BAGO.

## Arranque

1. Inicia BAGO API:

```powershell
python .\bago_core\launcher.py serve --port 8080
```

2. En otra terminal:

```powershell
cd ui-react
npm install
npm run dev
```

3. Build de producción:

```powershell
npm run build
```

Variables opcionales:

- `VITE_BAGO_API_URL` (en dev, por defecto usa `http://127.0.0.1:8080`)
- `VITE_BAGO_API_TOKEN`

## Arranque integrado

Si ya existe `ui-react\dist`, el backend la sirve automáticamente:

```powershell
python .\bago_core\launcher.py serve --port 8080
```

Opcionalmente puedes apuntar a otro bundle:

```powershell
python .\bago_core\launcher.py serve --port 8080 --ui-dist C:\ruta\dist
```

## Qué comparte

- La vista **Terminal** y la vista **Escritorio** usan la misma sesión backend.
- El chat y los slash commands pasan por el mismo bus HTTP (`/chat` y `/command`).
- El backend registra el canal de origen (`terminal` o `desktop`) en el shadow log.
- El catálogo puede operar en `all` para exploración y `available-only` para producción.
- Los comandos devuelven `message` y, cuando aplica, `data`/`plan` estructurados para la UI visual.
- `canary` y `full` siguen siendo modos futuros: hoy se comportan como observación segura.
