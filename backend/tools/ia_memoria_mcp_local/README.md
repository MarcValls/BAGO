# IA MEMORIA MCP LOCAL

Sistema local de memoria estructurada para ChatGPT Desktop, Codex CLI y la extensión de Codex mediante Model Context Protocol.

El paquete convierte un directorio autorizado en una memoria externa legible, versionable y auditable. ChatGPT no obtiene acceso arbitrario al ordenador: solo puede utilizar las herramientas definidas por el servidor MCP y únicamente dentro de la raíz configurada.

## Arquitectura

```text
ChatGPT general / Codex
        │
        │ MCP por STDIO
        ▼
IA Memoria MCP Local
        │
        ├── control de rutas
        ├── búsqueda e índice SQLite
        ├── propuesta y confirmación
        ├── estados y enlaces entre proyectos
        └── registro de eventos
        ▼
Directorio local IA_MEMORIA
```

Los documentos Markdown son la fuente legible. SQLite funciona como índice, catálogo y registro estructurado.

## Contenido

- Prompt de personalización para ChatGPT general.
- Kernel común de comportamiento y memoria.
- Servidor MCP local en Python.
- Índice SQLite reconstruible.
- Plantilla de proyectos.
- Proyectos iniciales: BAGO, IA. LA PREGUNTA, EDITORIAL, ARQUITECTURA y LABORATORIO.
- Enlaces interproyecto.
- Scripts de instalación, diagnóstico, reindexación y copia de seguridad.
- Configuración de ejemplo para ChatGPT Desktop y Codex.
- Pruebas de seguridad y persistencia.

## Requisitos

- Windows 10 o posterior.
- Python 3.10 o posterior.
- ChatGPT Desktop, Codex CLI o extensión Codex con MCP local.
- No se necesita una API key de OpenAI para el servidor local.

## Instalación rápida

Descomprime en una ubicación estable, por ejemplo:

```text
D:\IA_MEMORIA_MCP_LOCAL
```

Ejecuta:

```bat
scripts\install_windows.cmd
```

Después añade un servidor STDIO en ChatGPT Desktop:

```text
Comando:
D:\IA_MEMORIA_MCP_LOCAL\.venv\Scripts\python.exe

Argumentos:
-m
ia_memoria.server

Variable:
IA_MEMORY_ROOT=D:\IA_MEMORIA_MCP_LOCAL\memory_root
```

O con Codex CLI:

```bat
codex mcp add ia_memoria --env IA_MEMORY_ROOT=D:\IA_MEMORIA_MCP_LOCAL\memory_root -- D:\IA_MEMORIA_MCP_LOCAL\.venv\Scripts\python.exe -m ia_memoria.server
```

## Flujo de lectura

1. `get_context`
2. `get_project_state`
3. `memory_search`
4. `memory_read` para el documento preciso.

## Flujo de escritura

1. `memory_propose`
2. revisión del usuario
3. `memory_commit`
4. `record_event`
5. actualización del canon cuando proceda.

No se incluyen herramientas de shell, red, lectura arbitraria o borrado masivo.

## Versión

`0.1.0`, basada en la línea estable 1.x del SDK oficial MCP: `mcp>=1.28.1,<2`.
