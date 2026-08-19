// friendly-error.ts
// Normaliza mensajes de red/error en textos útiles para la UI.

const NETWORK_KEYS = ['failed to fetch', 'networkerror', 'err_connection_refused', 'cors', 'cors error'];

export function friendlyErrorMessage(error: unknown, fallback?: string): string {
  const raw = error instanceof Error ? error.message : String(error);
  const lower = raw.toLowerCase();
  if (NETWORK_KEYS.some((key) => lower.includes(key))) {
    return 'No se pudo conectar con BAGO. Comprueba que el backend está ejecutándose y que el origen está permitido.';
  }
  if (lower.includes('abort')) {
    return 'La solicitud fue cancelada.';
  }
  if (!raw || raw === 'undefined' || raw === 'null') {
    return fallback ?? 'Ha ocurrido un error inesperado.';
  }
  return fallback && raw.toLowerCase() === 'error' ? fallback : raw;
}
