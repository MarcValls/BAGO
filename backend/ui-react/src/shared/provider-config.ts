// provider-config.ts
// Modelo compuesto para describir proveedores en BAGO.
// provider + protocol + auth_kind + runtime_kind + secret_ref + model_discovery + billing_owner
// Auth y protocolo son ortogonales: el auth_kind NO incluye openai_compat (eso es protocolo).

export type AuthKind =
  | 'auth_none_local'         // loopback sin clave (solo 127.0.0.1)
  | 'auth_api_key'            // bearer estático
  | 'auth_api_key_scoped'     // con scope/workspace/proyecto
  | 'auth_oauth_browser'      // OAuth con callback (GitHub Copilot, OpenRouter PKCE)
  | 'auth_device_flow'        // RFC 8628 device authorization grant
  | 'auth_iam_cloud'          // AWS IAM / GCP ADC / Azure Entra / service account
  | 'auth_wif_workload'       // Workload Identity Federation
  | 'auth_delegated_runtime'  // CLI ya autenticado (Codex CLI, Copilot CLI)
  | 'auth_openai_compat';     // base_url + key opcional, para compat legacy

export type Protocol =
  | 'protocol_ollama'
  | 'protocol_openai'
  | 'protocol_anthropic'
  | 'protocol_google'
  | 'protocol_openai_compat'
  | 'protocol_github_models'
  | 'protocol_bedrock'
  | 'protocol_vertex';

export type RuntimeKind =
  | 'runtime_external'        // API remota
  | 'runtime_local_http'      // http://127.0.0.1:NNNN
  | 'runtime_local_cli'       // codex CLI, copilot CLI
  | 'runtime_proxy';          // BAGO actúa como proxy

export type ModelDiscovery =
  | { type: 'openai_models'; path: string }   // GET /v1/models
  | { type: 'ollama_tags'; path: string }     // GET /api/tags
  | { type: 'static_list'; models: string[] }
  | { type: 'manual' };                       // el usuario teclea

export interface ConnectivityTest {
  method: 'GET' | 'POST';
  path: string;
}

export interface ProviderDescriptor {
  provider_id: string;
  label: string;
  protocol: Protocol;
  auth_kind: AuthKind;
  runtime_kind: RuntimeKind;
  base_url?: string;
  // Referencia al secreto, no el secreto en sí.
  // En Fase A: TODO(secret_store): mover a backend/keyring.
  secret_ref?: string;
  model_discovery: ModelDiscovery;
  test?: ConnectivityTest;
  billing_owner: 'user' | 'org' | 'bago';
  enabled: boolean;
  // Notas de seguridad/UX que la UI muestra al configurar este provider.
  notes?: string[];
  // Campos legacy que el endpoint /providers/configure actual entiende.
  // En Fase A los seguimos mandando para no romper el backend.
  legacy?: { api_key?: string; default_model?: string };
}
