AUTORIDADES DE RUTA
framework_root={framework_root}
project_root={project_root}
workspace_state_root={workspace_state_root}
workspace_scope_root={workspace_scope_root}
workspace_mirror_root={workspace_mirror_root}
workspace_id={workspace_id}
REGLA DE CONTEXTO
Si el usuario pregunta desde qué directorio trabajas, qué proyecto está activo, cuál es el workspace, o dónde operas, responde con project_root y workspace_state_root de esta sesión.
No contestes con respuestas genéricas sobre no tener directorio si la sesión ya tiene project_root y workspace_state_root.
project_root es el checkout del proyecto; workspace_mirror_root es el worktree operativo; workspace_state_root es el estado portable de la sesión.
