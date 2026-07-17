(function () {
  const originalFetch = window.fetch.bind(window);

  function normalizePayload(payload) {
    if (!payload || typeof payload !== 'object') return { payload, changed: false };
    let changed = false;

    const status = payload.status && typeof payload.status === 'object' ? payload.status : null;
    const session = payload.session && typeof payload.session === 'object' ? payload.session : null;
    const binding = session && session.binding && typeof session.binding === 'object' ? session.binding : null;
    const workspaceState = status && typeof status.workspace_state === 'object'
      ? status.workspace_state
      : session && session.workspace_state && typeof session.workspace_state === 'object'
        ? session.workspace_state
        : null;

    const confirmed = Boolean(
      (workspaceState && workspaceState.binding_confirmed)
      || (binding && binding.binding_confirmed)
      || (status && status.binding_confirmed)
    );
    const reason = String(
      (workspaceState && workspaceState.binding_reason)
      || (binding && binding.binding_reason)
      || (status && status.binding_reason)
      || ''
    );

    if (status && confirmed && status.binding_confirmed !== true) {
      status.binding_confirmed = true;
      changed = true;
    }
    if (status && reason && status.binding_reason !== reason) {
      status.binding_reason = reason;
      changed = true;
    }
    if (binding && confirmed && binding.binding_confirmed !== true) {
      binding.binding_confirmed = true;
      changed = true;
    }
    if (binding && reason && !binding.binding_reason) {
      binding.binding_reason = reason;
      changed = true;
    }

    return { payload, changed };
  }

  window.fetch = async function patchedFetch(input, init) {
    const response = await originalFetch(input, init);
    try {
      const url = typeof input === 'string' ? input : String(input && input.url || '');
      if (!/(\/api\/v1\/ui\/bootstrap|\/status|\/session)(\?|$)/.test(url)) {
        return response;
      }

      const text = await response.clone().text();
      if (!text) return response;

      const payload = JSON.parse(text);
      const normalized = normalizePayload(payload);
      if (!normalized.changed) return response;

      const headers = new Headers(response.headers);
      if (!headers.has('content-type')) headers.set('content-type', 'application/json; charset=utf-8');
      return new Response(JSON.stringify(normalized.payload), {
        status: response.status,
        statusText: response.statusText,
        headers
      });
    } catch {
      return response;
    }
  };
})();
