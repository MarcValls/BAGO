import { useState, useEffect, useCallback, useRef } from 'react';
import type { BagoClient } from '@/api/client';
import type { GitHubAuthState } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';

interface Props {
  client: BagoClient;
  onClose: () => void;
}

const STATUS_LABELS: Record<string, string> = {
  checking: 'Verificando...',
  cli_unavailable: 'CLI de GitHub no encontrado',
  unauthenticated: 'No autenticado',
  authenticating: 'Autenticando...',
  authenticated: 'Autenticado',
  error: 'Error',
};

const CREDENTIAL_STORAGE_LABELS: Record<string, string> = {
  secure: 'Almacenamiento seguro',
  plaintext: 'Almacenamiento en texto plano',
  unknown: 'Desconocido',
};

const AUTH_POLL_INTERVAL_MS = 2_000;
const AUTH_POLL_ATTEMPTS = 60;

export function GitHubAuthPanel({ client, onClose }: Props) {
  const [authState, setAuthState] = useState<GitHubAuthState | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmLogout, setConfirmLogout] = useState(false);
  const authPollGeneration = useRef(0);

  useEffect(() => () => {
    authPollGeneration.current += 1;
  }, []);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const state = await client.getGitHubAuthStatus();
      setAuthState(state);
    } catch (e: unknown) {
      setError(friendlyErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleAuthenticate = useCallback(async () => {
    const generation = authPollGeneration.current + 1;
    authPollGeneration.current = generation;
    setActionLoading('authenticate');
    setError(null);
    try {
      const started = await client.startGitHubAuth();
      if (started.authenticated) {
        await loadStatus();
        return;
      }
      if (started.installed === false || started.error) {
        throw new Error(started.error || 'GitHub CLI no está disponible');
      }

      for (let attempt = 0; attempt < AUTH_POLL_ATTEMPTS; attempt += 1) {
        if (authPollGeneration.current !== generation) return;
        const state = await client.refreshGitHubAuth();
        if (authPollGeneration.current !== generation) return;
        setAuthState(state);
        if (state.authenticated) return;
        await new Promise((resolve) => window.setTimeout(resolve, AUTH_POLL_INTERVAL_MS));
      }
      setError('La autorización sigue pendiente. Puedes volver a intentarlo cuando termines en GitHub.');
    } catch (e: unknown) {
      if (authPollGeneration.current === generation) setError(friendlyErrorMessage(e));
    } finally {
      if (authPollGeneration.current === generation) setActionLoading(null);
    }
  }, [client, loadStatus]);

  const cancelAuthenticationWait = useCallback(() => {
    authPollGeneration.current += 1;
    setActionLoading(null);
    setError(null);
  }, []);

  const handleRefresh = useCallback(async () => {
    setActionLoading('refresh');
    setError(null);
    try {
      const state = await client.refreshGitHubAuth();
      setAuthState(state);
    } catch (e: unknown) {
      setError(friendlyErrorMessage(e));
    } finally {
      setActionLoading(null);
    }
  }, [client]);

  const handleLogout = useCallback(async () => {
    setConfirmLogout(false);
    setActionLoading('logout');
    setError(null);
    try {
      await client.logoutGitHub();
      await loadStatus();
    } catch (e: unknown) {
      setError(friendlyErrorMessage(e));
    } finally {
      setActionLoading(null);
    }
  }, [client, loadStatus]);

  const getStatusState = (): string => {
    if (!authState) return 'checking';
    if (!authState.installed) return 'cli_unavailable';
    if (authState.error) return 'error';
    if (authState.authenticated) return 'authenticated';
    return 'unauthenticated';
  };

  return (
    <div className="github-auth-panel" role="region" aria-label="Configuración de GitHub">
      <div className="panel-header">
        <h3>GitHub</h3>
        <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Cerrar">
          <Icon name="close" size={16} />
        </button>
      </div>

      <div className="github-auth-body">
        {loading && (
          <div className="panel-loading">
            <Icon name="refresh" size={16} className="spin" />
            <span>Verificando estado de GitHub...</span>
          </div>
        )}

        {!loading && error && (
          <div className="form-error" role="alert">
            <Icon name="alert" size={14} />
            <span>{error}</span>
            <button type="button" className="btn-link" onClick={loadStatus}>Reintentar</button>
          </div>
        )}

        {!loading && authState && !error && (
          <>
            {/* Status card */}
            <div className="github-status-card">
              <div className="github-status-icon">
                <Icon
                  name={authState.authenticated ? 'check' : authState.error ? 'alert' : 'warning'}
                  size={24}
                  style={{
                    color: authState.authenticated
                      ? 'var(--color-success)'
                      : authState.error
                      ? 'var(--color-error)'
                      : 'var(--color-warning)',
                  }}
                />
              </div>
              <div className="github-status-info">
                <span className="github-status-label">
                  {STATUS_LABELS[getStatusState()] || getStatusState()}
                </span>
                {authState.hostname && (
                  <span className="github-status-host">Host: {authState.hostname}</span>
                )}
                {authState.username && (
                  <span className="github-status-user">@{authState.username}</span>
                )}
              </div>
            </div>

            {/* Authenticated details */}
            {authState.authenticated && (
              <div className="github-details-card">
                <div className="github-detail-row">
                  <span className="github-detail-label">Cuenta activa</span>
                  <span className="github-detail-value">{authState.activeAccount || authState.username || '—'}</span>
                </div>
                <div className="github-detail-row">
                  <span className="github-detail-label">Scopes</span>
                  <span className="github-detail-value">
                    {authState.scopes?.length ? authState.scopes.join(', ') : '—'}
                  </span>
                </div>
                <div className="github-detail-row">
                  <span className="github-detail-label">Almacenamiento</span>
                  <span className="github-detail-value">
                    {authState.credentialStorage ? CREDENTIAL_STORAGE_LABELS[authState.credentialStorage] || authState.credentialStorage : '—'}
                  </span>
                </div>
                <div className="github-detail-row">
                  <span className="github-detail-label">Última verificación</span>
                  <span className="github-detail-value">
                    {authState.checkedAt ? new Date(authState.checkedAt).toLocaleString() : '—'}
                  </span>
                </div>
              </div>
            )}

            {/* CLI unavailable */}
            {getStatusState() === 'cli_unavailable' && (
              <div className="github-cli-unavailable">
                <Icon name="warning" size={20} style={{ color: 'var(--color-warning)' }} />
                <p>El CLI de GitHub (<code>gh</code>) no está instalado o no se encuentra en el PATH.</p>
                <p>BAGO necesita <code>gh</code> para interactuar con tu cuenta de GitHub.</p>
                <a
                  href="https://cli.github.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn--secondary"
                >
                  Instalar GitHub CLI
                </a>
              </div>
            )}

            {/* Error state */}
            {getStatusState() === 'error' && (
              <div className="github-error-detail">
                <Icon name="alert" size={16} style={{ color: 'var(--color-error)' }} />
                <span>{authState.error}</span>
              </div>
            )}

            {/* Actions */}
            <div className="github-actions">
              {authState.installed && !authState.authenticated && (
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={handleAuthenticate}
                  disabled={actionLoading !== null}
                >
                  <Icon name="link" size={14} />
                  {actionLoading === 'authenticate' ? 'Esperando autorización...' : 'Conectar con GitHub'}
                </button>
              )}

              {actionLoading === 'authenticate' && (
                <div className="github-auth-progress" role="status">
                  <span>Completa la autorización en GitHub. BAGO detectará la sesión automáticamente.</span>
                  <button type="button" className="btn-link" onClick={cancelAuthenticationWait}>Dejar de esperar</button>
                </div>
              )}

              {authState.authenticated && (
                <>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    onClick={handleRefresh}
                    disabled={actionLoading !== null}
                  >
                    <Icon name="refresh" size={14} />
                    {actionLoading === 'refresh' ? 'Refrescando...' : 'Refrescar estado'}
                  </button>
                  {!confirmLogout ? (
                    <button
                      type="button"
                      className="btn btn--danger"
                      onClick={() => setConfirmLogout(true)}
                      disabled={actionLoading !== null}
                    >
                      <Icon name="close" size={14} />
                      {actionLoading === 'logout' ? 'Cerrando...' : 'Cerrar sesión'}
                    </button>
                  ) : (
                    <div className="inline-confirm" role="group" aria-label="Confirmar cierre de sesión">
                      <span className="inline-confirm-label">¿Cerrar sesión de GitHub?</span>
                      <button type="button" className="btn btn--ghost" onClick={() => setConfirmLogout(false)}>Cancelar</button>
                      <button type="button" className="btn btn--danger" onClick={handleLogout}>Sí, cerrar</button>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="github-security-note">
              <Icon name="shield" size={12} />
              <span>Las credenciales se gestionan mediante <code>gh auth</code>. BAGO nunca almacena tokens en texto plano.</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
