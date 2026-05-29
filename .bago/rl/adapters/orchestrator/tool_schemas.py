# -*- coding: utf-8 -*-
"""tool_schemas.py — Schemas JSON de las 5 herramientas BAGO expuestas al LLM."""
from __future__ import annotations

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bago_search",
            "description": (
                "Búsqueda semántica por palabra clave, sinónimos y metáforas "
                "en el código del proyecto. Útil cuando el usuario busca algo "
                "sin saber el nombre exacto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "Palabra clave o concepto a buscar"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directorio raíz de búsqueda (default: repo root)"
                    },
                    "synonyms": {
                        "type": "boolean",
                        "description": "Expandir con sinónimos (es/en)"
                    },
                    "metaphors": {
                        "type": "boolean",
                        "description": "Incluir metáforas y expresiones relacionadas"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_list",
            "description": (
                "Lista archivos del proyecto con filtros contextuales. "
                "Útil para explorar estructura, tamaños, o estado git."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directorio a listar"
                    },
                    "tree": {
                        "type": "boolean",
                        "description": "Mostrar en formato árbol"
                    },
                    "git": {
                        "type": "boolean",
                        "description": "Incluir estado git (modified, untracked)"
                    },
                    "sizes": {
                        "type": "boolean",
                        "description": "Incluir tamaños de archivo"
                    },
                    "json": {
                        "type": "boolean",
                        "description": "Salida JSON para procesamiento"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_read",
            "description": (
                "Lee un archivo con resaltado de sintaxis y contexto inteligente. "
                "Útil cuando el usuario pregunta 'muestrame el codigo de X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Ruta al archivo a leer"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Número de líneas a mostrar (default: 50)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Contexto adicional para resaltar (ej: 'function calls')",
                        "enum": ["none", "functions", "imports", "comments", "config"]
                    }
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_call_search",
            "description": (
                "Busca definiciones de funciones, clases, o llamadas API "
                "con análisis por lenguaje de programación. "
                "Útil para 'dónde se define X' o 'quién llama a Y'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nombre de función, clase, o patrón"
                    },
                    "lang": {
                        "type": "string",
                        "description": "Lenguaje: python, javascript, typescript, rust, go",
                        "enum": ["python", "javascript", "typescript", "rust", "go", "all"]
                    },
                    "def": {
                        "type": "boolean",
                        "description": "Buscar definiciones (True) o llamadas (False)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bago_grep_smart",
            "description": (
                "Grep inteligente con filtros de contexto de código. "
                "Útil para búsquedas de patrón avanzadas con contexto semántico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Patrón regex a buscar"
                    },
                    "def": {
                        "type": "boolean",
                        "description": "Limitar a definiciones de función/clase"
                    },
                    "call": {
                        "type": "boolean",
                        "description": "Limitar a llamadas de función"
                    },
                    "import": {
                        "type": "boolean",
                        "description": "Limitar a imports/usos de módulo"
                    },
                    "ext": {
                        "type": "string",
                        "description": "Extensiones a filtrar, ej: py,ts,md"
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]

TOOL_NAMES = [s["function"]["name"] for s in TOOL_SCHEMAS]
