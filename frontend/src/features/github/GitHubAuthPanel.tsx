import { useEffect, useState } from 'react';
import { Icon } from '@/shared/Icon';

interface GitHubAccount {
  username?: string;
  name?: string;
  active: boolean;
  hostname?: string;
}

interface GitHubAuthState {
  installed: boolean;
  authenticated: boolean;
  hostname?: string;
  username?: string;
  activeAccount?: string;
  scopes: string[];
  credentialStorage: string;
  error?: string;
  checkedAt: string;
}

interface GitHubAuthPanelProps {
  client?: ReturnType<typeof import('@/api/client').createBagoClient>;
  onClose?: () => void;
}

export function GitHubAuthPanel({ client, onClose }: GitHubAuthPanelProps) {
  const [state, setState] = useState<GitHubAuthState | null>(null);
  const [accounts, setAccounts] = useState<GitHubAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(false);
  const [gitEmail, setGitEmail] = useState('');
  const [gitUsername, setGitUsername] = useState('');
  const [gitConfigured, setGitConfigured] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function loadStatus() {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      const [statusRes, accountsRes] = await Promise.all([
        client.getGitHubAuthStatus(),
        client.getGitHubAccounts(),
      ]);
      setState(statusRes as unknown as GitHubAuthState);
      if (accountsRes.accounts) setAccounts(accountsRes.accounts as unknown as GitHubAccount[]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadStatus(); }, [client]);

  async function handleLogin() {
    if (!client) return;
    setActionInProgress(true);
    setError(null);
    setNotice(null);
    try {
      const res = await client.startGitHubAuth() as { authenticated?: boolean; pending?: boolean; message?: string; error?: string };
      if (res.error) setError(res.error);
      if (res.pending) setNotice(res.message || 'Completa la autorización en el navegador y pulsa Refrescar.');
      await loadStatus();
    } catch (e) {
      setError(String(e));
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleRefresh() {
    if (!client) return;
    setActionInProgress(true);
    setError(null);
    setNotice(null);
    try {
      await client.refreshGitHubAuth();
      await loadStatus();
    } catch (e) {
      setError(String(e));
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleLogout() {
    if (!client || !state?.hostname) return;
    if (!confirm('¿Cerrar sesión de GitHub?')) return;
    setActionInProgress(true);
    setError(null);
    setNotice(null);
    try {
      await client.logoutGitHub(state.hostname);
      await loadStatus();
    } catch (e) {
      setError(String(e));
    } finally {
      setActionInProgress(false);
    }
  }

  async function handleSetupGit() {
    if (!client || !gitEmail.trim() || !gitUsername.trim()) return;
    setActionInProgress(true);
    setError(null);
    try {
      const res = await client.setupGitGitHub(gitEmail.trim(), gitUsername.trim()) as { ok: boolean; configured?: boolean; errors?: string[] };
      if (res.configured) {
        setGitConfigured(true);
      } else {
        setError((res.errors || []).join(', '));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setActionInProgress(false);
    }
  }

  function renderCredentialBadge(storage: string) {
    const map: Record<string, { label: string; className: string }> = {
      secure: { label: '🔒 Seguro', className: 'badge-secure' },
      plaintext: { label: '⚠️ Texto plano', className: 'badge-warning' },
      unknown: { label: '❓ Desconocido', className: 'badge-unknown' },
    };
    const badge = map[storage] || map.unknown;
    return <span className={`credential-badge ${badge.className}`}>{badge.label}</span>;
  }

  if (loading && !state) {
    return (
      <div className="panel github-auth-panel">
        <div className="panel-header">
          <span className="panel-title">GitHub Auth</span>
          <button type="button" className="btn-icon" onClick={onClose}><Icon name="x" /></button>
        </div>
        <div className="panel-loading">Cargando...</div>
      </div>
    );
  }

  return (
    <div className="panel github-auth-panel">
      <div className="panel-header">
        <span className="panel-title">GitHub Auth</span>
        <button type="button" className="btn-icon" onClick={onClose} title="Cerrar"><Icon name="x" /></button>
      </div>

      <div className="panel-body">
        {!state?.installed ? (
          <div className="auth-not-installed">
            <Icon name="github" size={32} />
            <p>gh CLI no está instalado.</p>
            <a href="https://cli.github.com/" target="_blank" rel="noreferrer">
              Instalar GitHub CLI
            </a>
          </div>
        ) : !state.authenticated ? (
          <div className="auth-unauthenticated">
            <Icon name="github" size={32} />
            <p>No has iniciado sesión en GitHub.</p>
            {notice && <div className="form-notice">{notice}</div>}
            {error && <div className="form-error">{error}</div>}
            <button
              type="button"
              className="btn-primary"
              onClick={handleLogin}
              disabled={actionInProgress}
            >
              {actionInProgress ? 'Conectando...' : 'Iniciar sesión con gh'}
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={handleRefresh}
              disabled={actionInProgress}
            >
              Refrescar estado
            </button>
          </div>
        ) : (
          <div className="auth-authenticated">
            <div className="auth-status-card">
              <div className="status-row">
                <Icon name="check-circle" className="status-icon ok" />
                <span>Autenticado como <strong>{state.username || state.activeAccount}</strong></span>
              </div>
              {state.hostname && (
                <div className="status-row">
                  <span className="status-label">Host:</span>
                  <span>{state.hostname}</span>
                </div>
              )}
              <div className="status-row">
                <span className="status-label">Token:</span>
                {renderCredentialBadge(state.credentialStorage)}
              </div>
              {state.scopes.length > 0 && (
                <div className="status-row scopes">
                  <span className="status-label">Scopes:</span>
                  <div className="scopes-list">
                    {state.scopes.map((scope) => (
                      <span key={scope} className="scope-tag">{scope}</span>
                    ))}
                  </div>
                </div>
              )}
              <div className="status-row">
                <span className="status-label">Verificado:</span>
                <span>{state.checkedAt ? new Date(state.checkedAt).toLocaleString() : 'N/A'}</span>
              </div>
            </div>

            {error && <div className="form-error">{error}</div>}

            <div className="auth-actions">
              <button type="button" className="btn-secondary" onClick={handleRefresh} disabled={actionInProgress}>
                <Icon name="refresh" />
                Refrescar
              </button>
              <button type="button" className="btn-danger" onClick={handleLogout} disabled={actionInProgress}>
                <Icon name="x-circle" />
                Cerrar sesión
              </button>
            </div>

            {accounts.length > 0 && (
              <div className="accounts-section">
                <h4>Cuentas configuradas</h4>
                {accounts.map((acct, i) => (
                  <div key={i} className={`account-row ${acct.active ? 'is-active' : ''}`}>
                    <Icon name={acct.active ? 'check-circle' : 'circle'} className={acct.active ? 'ok' : ''} />
                    <span className="acct-name">{acct.name || acct.username}</span>
                    <span className="acct-user">@{acct.username}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="git-setup-section">
              <h4>Configurar git</h4>
              <div className="form-field">
                <label>Email</label>
                <input
                  type="email"
                  value={gitEmail}
                  onChange={(e) => setGitEmail(e.target.value)}
                  placeholder="tu@email.com"
                />
              </div>
              <div className="form-field">
                <label>Username</label>
                <input
                  type="text"
                  value={gitUsername}
                  onChange={(e) => setGitUsername(e.target.value)}
                  placeholder="tu-usuario-github"
                />
              </div>
              {gitConfigured ? (
                <div className="git-configured-ok">✓ Git configurado correctamente</div>
              ) : (
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleSetupGit}
                  disabled={actionInProgress || !gitEmail.trim() || !gitUsername.trim()}
                >
                  Configurar git
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
