// provider-catalog.ts
// Catálogo BAGO de proveedores. Orden de prioridad Fase A:
//  1) ollama-local
//  2) ollama-cloud
//  3) codex (delegated)
//  4) openai
//  5) github-copilot (OAuth)
//  6) github-copilot (delegated CLI)
// Después: el resto coherente.

import { ProviderDescriptor } from './provider-config';

export const PROVIDER_CATALOG: ProviderDescriptor[] = [
  // ─── 1. Ollama local ────────────────────────────────────────────────
  {
    provider_id: 'ollama-local',
    label: 'Ollama local',
    protocol: 'protocol_ollama',
    auth_kind: 'auth_none_local',
    runtime_kind: 'runtime_local_http',
    base_url: 'http://localhost:11434',
    model_discovery: { type: 'ollama_tags', path: '/api/tags' },
    test: { method: 'GET', path: '/api/tags' },
    billing_owner: 'user',
    enabled: true,
    notes: [
      'Sin autenticación en loopback.',
      'Si expones Ollama por red, configura un proxy o token propio.'
    ]
  },

  // ─── 2. Ollama cloud ────────────────────────────────────────────────
  {
    provider_id: 'ollama-cloud',
    label: 'Ollama Cloud',
    protocol: 'protocol_ollama',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://ollama.com',
    model_discovery: { type: 'openai_models', path: '/v1/models' },
    test: { method: 'GET', path: '/v1/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'Si hiciste "ollama signin" local, también puedes usar la sesión local.',
      'Pega aquí tu OLLAMA_API_KEY para llamadas directas a ollama.com.'
    ]
  },

  // ─── 3. OpenAI Codex (delegated runtime) ────────────────────────────
  {
    provider_id: 'codex',
    label: 'OpenAI Codex (CLI)',
    protocol: 'protocol_openai',
    auth_kind: 'auth_delegated_runtime',
    runtime_kind: 'runtime_local_cli',
    model_discovery: { type: 'manual' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'BAGO delega en el Codex CLI ya autenticado.',
      'Si no se detecta el CLI, se ofrece instalarlo.'
    ]
  },

  // ─── 4. OpenAI Platform ─────────────────────────────────────────────
  {
    provider_id: 'openai',
    label: 'OpenAI Platform',
    protocol: 'protocol_openai',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.openai.com/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    test: { method: 'GET', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'La clave se guarda en el backend, nunca en el bundle del frontend.',
      'OpenAI distingue Codex (suscripción ChatGPT) de Platform (facturado por API).'
    ]
  },

  // ─── 5. GitHub Copilot (OAuth por usuario) ──────────────────────────
  {
    provider_id: 'github-copilot-oauth',
    label: 'GitHub Copilot (OAuth)',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_oauth_browser',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.githubcopilot.com',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'Cada usuario registra su propia GitHub OAuth App.',
      'BAGO abre el navegador, recibe el callback y guarda el token cifrado.'
    ]
  },

  // ─── 6. GitHub Copilot (delegated CLI) ──────────────────────────────
  {
    provider_id: 'github-copilot-cli',
    label: 'GitHub Copilot (CLI)',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_delegated_runtime',
    runtime_kind: 'runtime_local_cli',
    model_discovery: { type: 'manual' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'BAGO delega en el Copilot CLI ya autenticado.',
      'Si no se detecta, se ofrece instalarlo.'
    ]
  },

  // ─── Resto coherente ────────────────────────────────────────────────
  {
    provider_id: 'anthropic',
    label: 'Anthropic Claude',
    protocol: 'protocol_anthropic',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.anthropic.com',
    model_discovery: { type: 'manual' },
    test: { method: 'GET', path: '/v1/models' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'openrouter',
    label: 'OpenRouter',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://openrouter.ai/api/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    test: { method: 'GET', path: '/models' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'google-gemini',
    label: 'Google Gemini (AI Studio)',
    protocol: 'protocol_google',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://generativelanguage.googleapis.com',
    model_discovery: { type: 'manual' },
    test: { method: 'GET', path: '/v1beta/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'API key estándar de Google AI Studio.',
      'Google está migrando a auth keys con restricciones; revisa las del proyecto.'
    ]
  },
  {
    provider_id: 'vertex-ai',
    label: 'Vertex AI (GCP IAM)',
    protocol: 'protocol_vertex',
    auth_kind: 'auth_iam_cloud',
    runtime_kind: 'runtime_external',
    base_url: 'https://{location}-aiplatform.googleapis.com',
    model_discovery: { type: 'manual' },
    billing_owner: 'org',
    enabled: false,
    notes: [
      'Application Default Credentials, service account o Workload Identity.',
      'Pedirá: project_id, location, credentials_ref.'
    ]
  },
  {
    provider_id: 'azure-openai',
    label: 'Azure OpenAI',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_iam_cloud',
    runtime_kind: 'runtime_external',
    model_discovery: { type: 'manual' },
    billing_owner: 'org',
    enabled: false,
    notes: [
      'API key en header api-key, o Microsoft Entra ID.',
      'Pedirá: endpoint, deployment, api_version, api_key o entra_token.'
    ]
  },
  {
    provider_id: 'aws-bedrock',
    label: 'AWS Bedrock',
    protocol: 'protocol_bedrock',
    auth_kind: 'auth_iam_cloud',
    runtime_kind: 'runtime_external',
    model_discovery: { type: 'manual' },
    billing_owner: 'org',
    enabled: false,
    notes: [
      'IAM/AWS credentials o API key bearer.',
      'Pedirá: region, profile/role, opcional bedrock_api_key.'
    ]
  },
  {
    provider_id: 'huggingface',
    label: 'Hugging Face',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://router.huggingface.co/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'Token HF con permiso "Make calls to Inference Providers".'
    ]
  },
  {
    provider_id: 'mistral',
    label: 'Mistral',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.mistral.ai/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'groq',
    label: 'Groq',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.groq.com/openai/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'deepseek',
    label: 'DeepSeek',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.deepseek.com',
    model_discovery: { type: 'manual' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'xai',
    label: 'xAI (Grok)',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_external',
    base_url: 'https://api.x.ai/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false
  },
  {
    provider_id: 'llama-cpp-local',
    label: 'llama.cpp server',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_local_http',
    base_url: 'http://localhost:8080/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'Solo loopback. Si arrancaste con --api-key, introdúcelo.',
      'Para red: no expongas sin proxy o token.'
    ]
  },
  {
    provider_id: 'vllm-local',
    label: 'vLLM local',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_api_key',
    runtime_kind: 'runtime_local_http',
    base_url: 'http://localhost:8000/v1',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'vLLM advierte que --api-key no protege todos los endpoints sensibles.'
    ]
  },
  {
    provider_id: 'custom-openai-compatible',
    label: 'Compatible OpenAI (custom)',
    protocol: 'protocol_openai_compat',
    auth_kind: 'auth_openai_compat',
    runtime_kind: 'runtime_external',
    model_discovery: { type: 'openai_models', path: '/models' },
    billing_owner: 'user',
    enabled: false,
    notes: [
      'provider_id, base_url, api_key opcional, headers, modelos autodetectados o manuales.'
    ]
  }
];

export function findProvider(id: string): ProviderDescriptor | undefined {
  return PROVIDER_CATALOG.find((p) => p.provider_id === id);
}
