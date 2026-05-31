# Contrato de Presentación y Distribución de Archivos en GitHub

## 1. Propósito
Este contrato define las reglas, responsabilidades y criterios de calidad para la publicación de código fuente, documentación y artefactos de BAGO en su repositorio oficial de GitHub (`MarcValls/BAGO`). Su objetivo es garantizar que cada commit que llega a la rama principal sea reproducible, profesional y seguro.

## 2. Filosofía de Distribución
- **Solo lo necesario**: el repositorio contiene únicamente lo indispensable para instalar, ejecutar y validar BAGO.
- **Sin estado mutable**: credenciales, cachés, logs, `node_modules`, `__pycache__` y archivos temporales están estrictamente prohibidos en el árbol de fuentes.
- **Evidencia antes que promesa**: cada funcionalidad distribuida debe poder validarse con los tests y comandos de gate documentados.

## 3. Estructura de Directorios y Responsabilidades

| Directorio | Responsabilidad | Reglas de Contenido |
|------------|----------------|---------------------|
| `.bago/chat/` | REPL, renderizado y prompts de sistema | Solo código fuente Python. Sin snapshots de terminal. |
| `.bago/core/` | Motor de sesiones, registro de herramientas, compresión de contexto, RL | Módulos autónomos con docstrings. Sin datos de usuario. |
| `.bago/providers/` | Adaptadores de proveedores LLM | Un archivo por proveedor. Sin API keys hardcodeadas. |
| `.bago/api/` | API REST local (opcional) | Documentar endpoints en `docs/ARCHITECTURE.md`. |
| `bago_core/` | CLI legacy y runtime auxiliar | Mantener para compatibilidad; migrar progresivamente a `.bago/`. |
| `docs/` | Documentación del proyecto | Markdown profesional. Sin capturas de pantalla brute-force. |
| `scripts/` | Scripts de utilidad registrados | Deben tener shebang, docstring y manejo de errores. |
| `tests/` | Validación automatizada | Cada gate de release debe ejecutarse sin fallos. |

## 4. Archivos Prohibidos
Los siguientes tipos de archivo nunca deben aparecer en un commit de distribución:
- Logs de terminal (`repl_capture_*.txt`, `terminal_captures.txt`).
- Archivos de credenciales o tokens (`.env`, `secrets.json`).
- Directorios de dependencias instaladas (`node_modules/`, `venv/`, `__pycache__/`).
- Artefactos de build temporales (`*.pyc`, `*.egg-info`, `dist/`, `build/`).
- Archivos de estado personal del usuario (`*.db`, `*.sqlite3`, sesiones locales).

## 5. Control de Calidad Pre-Push
Antes de cualquier push a `main`, el mantenedor debe ejecutar:
```powershell
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
```
Si alguno de los tres falla, el push está bloqueado hasta su resolución.

## 6. Versionado y Releases
- Las releases siguen SemVer (`v4.x.x`).
- Cada release debe incluir:
  - Un tag firmado (`git tag -s`).
  - Notas de release en GitHub con secciones: Novedades, Correcciones, Breaking Changes.
  - Un paquete de instalación validado (`install-v4.ps1` o script equivalente).

## 7. Seguridad
- Ningún secret o key debe residir en el historial de Git. Si ocurre, se debe rotar el secret y purgar el historial (`git filter-repo` o BFG).
- Los scripts de instalación no deben ejecutar comandos arbitrarios sin confirmación explícita del usuario.
- El proveedor `cpp-local` y cualquier runtime experimental deben estar ocultos por defecto en la ruta principal.

## 8. Proceso de Actualización Profesional
1. **Sincronización**: copiar los cambios validados desde el entorno de desarrollo local al working tree.
2. **Limpieza**: eliminar archivos basura y verificar `.gitignore`.
3. **Documentación**: actualizar `README.md`, `MANUAL.md` y `docs/ROADMAP.md` si hay cambios de alcance.
4. **Validación**: ejecutar los tres gates de seguridad.
5. **Commit**: mensaje claro en inglés o español con referencia al área modificada (`core:`, `chat:`, `docs:`).
6. **Push**: directo a `main` solo si los gates pasan; de lo contrario, pull request.

## 9. Firma y Vigencia
Este contrato entra en vigor en el momento de su commit a `docs/DISTRIBUTION_CONTRACT.md` y vincula a todos los contribuyentes del repositorio `MarcValls/BAGO`.

*Última actualización: 2026-05-31*
