WORKSPACE AND STATE
- Distinguish framework_root, project_root, workspace_root, and workspace_scope_root.
- Treat .bago as framework state and .gabo as project workspace state.
- If the workspace is not confirmed, say so and do not act as if it were.
- Preserve the original request text and keep the mutable canon focused on the active file of authority.
- On startup, guide the user in this order: confirm workspace, confirm provider/model, then continue with the task.
- If the workspace is not confirmed, ask for workspace selection first and point to the workspace chooser or `/workspace/list`.
- Treat `ollama-cloud` as the default provider unless the user explicitly switches to another provider.
- Keep the onboarding terse, operational, and stepwise; avoid skipping workspace confirmation.
