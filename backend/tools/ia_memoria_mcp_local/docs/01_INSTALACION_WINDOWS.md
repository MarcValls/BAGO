# Instalación en Windows

## Automática

```bat
scripts\install_windows.cmd
```

Crea `.venv`, instala, inicializa, diagnostica y muestra la configuración.

## Manual

```bat
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .
set IA_MEMORY_ROOT=%CD%\memory_root
ia-memoria-init
ia-memoria-doctor
```

## ChatGPT Desktop

Añade un servidor MCP STDIO con el Python del entorno virtual, argumentos `-m ia_memoria.server` y la variable `IA_MEMORY_ROOT`.

## Carpeta externa

Puedes mover `memory_root` a `D:\IA_MEMORIA` y cambiar solo la variable.

Se incluyen `.cmd` para no depender de la política de ejecución de PowerShell.
