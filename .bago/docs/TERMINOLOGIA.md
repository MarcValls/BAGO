# BAGO Terminología Oficial

## Jerarquía de Ejecución

    USUARIO
      |
      v
    [TAREA]  ──→  BAGO (Framework)
                      |
                      ├── Router Dinámico → Tipo de tarea
                      ├── Orquestador     → Agente + Modelo óptimos
                      └── Launcher        → Ejecuta
                      |
                      v
                  [AGENTE] ──→ Proveedor de ejecución
                      |
                      ├── codex        (OpenAI Codex CLI)
                      ├── copilot      (GitHub Copilot)
                      ├── ollama-local (Ollama offline)
                      └── ollama-cloud (Ollama cloud)
                      |
                      v
                  [MODELO] ──→ LLM específico
                      |
                      ├── gpt-5.5          (codex)
                      ├── claude-sonnet-4.6 (copilot)
                      ├── qwen2.5:0.5b     (ollama-local)
                      └── kimi-k2-1t       (ollama-cloud)
                      |
                      v
                  [RESULTADO]

## Definiciones

| Término    | Qué es                                      | Ejemplo                    |
|------------|---------------------------------------------|----------------------------|
| BAGO       | Framework de orquestación y launcher        | BAGO launch "tarea"      |
| Agente     | Proveedor/entidad de ejecución              | codex, copilot, ollama     |
| Modelo     | LLM específico dentro del agente            | gpt-5.4, claude-sonnet    |
| Router     | Componente BAGO que clasifica la tarea      | bago_dynamic_router.py / intent_router.py |
| Router de agentes | Componente BAGO que decide proveedor y modelo | agent_router.py / `bago route` |
| Orquestador| Componente BAGO que ejecuta workflows multi-tool | orchestrator.py       |
| Launcher   | Componente BAGO que ejecuta                 | bago.ps1 / bago.cmd        |
| Tarea      | Input del usuario                           | "transponer partitura"     |
| Rol        | Perfil BAGO asignado a la tarea             | GENERADOR_Contenido        |
| Tools      | Herramientas BAGO recomendadas              | tool_registry.py / `bago ask` |

## Regla de oro

- BAGO NUNCA es un modelo.
- BAGO NUNCA es un agente.
- BAGO es el DIRECTOR que elige qué AGENTE y qué MODELO ejecutan la tarea.
