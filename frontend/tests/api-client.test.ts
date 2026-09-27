import { afterEach, describe, expect, it, vi } from 'vitest';
import { createBagoClient } from '../src/api/client';

function authorizedClient() {
  const client = createBagoClient('', '');
  client.setAuthorizationConfirmation(async () => true);
  return client;
}

describe('BagoClient response parsing', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('replaces raw JSON parser failures with a stable backend error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html><title>Vite</title>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' }
    })));

    const request = createBagoClient('', '').sendChat('hola');

    await expect(request).rejects.toMatchObject({
      name: 'BagoHttpError',
      status: 200,
      message: 'La API de BAGO devolvió una respuesta no JSON. Comprueba la URL del backend.'
    });
  });

  it('keeps valid JSON responses unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, response: 'hola' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })));

    await expect(createBagoClient('', '').sendChat('hola')).resolves.toEqual({
      ok: true,
      response: 'hola'
    });
  });

  it('preserves attempted provider and model on backend chat failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false,
      error: 'El modelo agotó el tiempo',
      provider: 'ollama-local',
      model: 'granite3.2:8b'
    }), {
      status: 504,
      headers: { 'Content-Type': 'application/json' }
    })));

    await expect(createBagoClient('', '').sendChat('hola')).rejects.toMatchObject({
      name: 'BagoHttpError',
      status: 504,
      message: 'El modelo agotó el tiempo',
      provider: 'ollama-local',
      model: 'granite3.2:8b'
    });
  });

  it('marks context helper calls as internal', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, response: '{}' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('', '').sendInternalChat('revisa contexto');

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body).toMatchObject({ message: 'revisa contexto', internal: true, surface: 'context-internal' });
  });

  it('keeps streamed text and final receipt metadata together', async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"chunk":"Hola "}\n\ndata: {"chunk":"mundo"}\n\n'));
        controller.enqueue(encoder.encode('data: {"done":true,"response_state":"done","context_receipt":{"id":"r1"}}\n\n'));
        controller.close();
      }
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })));

    const chunks: string[] = [];
    const result = await createBagoClient('', '').streamChat('hola', (chunk) => chunks.push(chunk));

    expect(chunks.join('')).toBe('Hola mundo');
    expect(result).toMatchObject({ response: 'Hola mundo', response_state: 'done', context_receipt: { id: 'r1' } });
  });

  it('marks optional file reads explicitly in the request URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      exists: false,
      content: ''
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createBagoClient('', '').readFile('.bago/context/context-tree.json', { optional: true })).resolves.toMatchObject({
      ok: true,
      exists: false
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/files/read/.bago%2Fcontext%2Fcontext-tree.json?optional=1',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('uses the canonical BAGO token header for provider operations', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'idle' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('http://127.0.0.1:8080', 'session-token').getAutoConfigStatus();

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get('X-Bago-Token')).toBe('session-token');
    expect(headers.get('Authorization')).toBeNull();
  });

  it('clears a session model through challenge, approval and one-time permit', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      if (body.authorization_action === 'challenge') {
        return Promise.resolve(new Response(JSON.stringify({
          ok: true,
          authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-router-clear' } }
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      if (body.authorization_action === 'approve') {
        return Promise.resolve(new Response(JSON.stringify({
          ok: true,
          authorization: { state: 'authorized', permit: { token: 'permit-router-clear' } }
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return Promise.resolve(new Response(JSON.stringify({ ok: true, cleared: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().setSessionModel(null)).resolves.toMatchObject({ ok: true, cleared: true });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const bodies = fetchMock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>);
    expect(bodies.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(new Set(bodies.map((body) => body.interaction_id)).size).toBe(1);
    expect(bodies[1]).toMatchObject({ challenge_id: 'challenge-router-clear', user_decision: 'approve' });
    expect(bodies[2]).toMatchObject({ authorization_permit: 'permit-router-clear' });
  });

  it('persists a workspace through challenge, approval and one-time permit', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      if (body.authorization_action === 'challenge') {
        return Promise.resolve(new Response(JSON.stringify({
          ok: true,
          authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-workspace-bind' } }
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      if (body.authorization_action === 'approve') {
        return Promise.resolve(new Response(JSON.stringify({
          ok: true,
          authorization: { state: 'authorized', permit: { token: 'permit-workspace-bind' } }
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return Promise.resolve(new Response(JSON.stringify({ ok: true, saved: 'C:/work/project' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().persistWorkspace('C:/work/project')).resolves.toMatchObject({
      ok: true,
      saved: 'C:/work/project'
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const bodies = fetchMock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>);
    expect(bodies.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(new Set(bodies.map((body) => body.interaction_id)).size).toBe(1);
    expect(bodies.every((body) => body.path === 'C:/work/project')).toBe(true);
    expect(bodies[1]).toMatchObject({ challenge_id: 'challenge-workspace-bind', user_decision: 'approve' });
    expect(bodies[2]).toMatchObject({ authorization_permit: 'permit-workspace-bind' });
  });

  it('syncs the session mirror through challenge, approval and one-time permit', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      const payload = body.authorization_action === 'challenge'
        ? { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-mirror-sync' } } }
        : body.authorization_action === 'approve'
          ? { ok: true, authorization: { state: 'authorized', permit: { token: 'permit-mirror-sync' } } }
          : { ok: true, effect_id: 'workspace.mirror.sync' };
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().syncProject())
      .resolves.toMatchObject({ ok: true, effect_id: 'workspace.mirror.sync' });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.every(([url]) => url === '/project/sync')).toBe(true);
    const bodies = fetchMock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>);
    expect(bodies.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(bodies.every((body) => !('root' in body) && !('path' in body))).toBe(true);
    expect(new Set(bodies.map((body) => body.interaction_id)).size).toBe(1);
    expect(bodies[2]).toMatchObject({ authorization_permit: 'permit-mirror-sync' });
  });

  it('attaches context through challenge, approval and one-time permit', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      const payload = body.authorization_action === 'challenge'
        ? { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'context-challenge' } } }
        : body.authorization_action === 'approve'
          ? { ok: true, authorization: { state: 'authorized', permit: { token: 'context-permit' } } }
          : { ok: true, effect_id: 'workspace.context.attach', data: { file_count: 1 } };
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().attachContext(['folder with spaces/note.txt']))
      .resolves.toMatchObject({ ok: true, effect_id: 'workspace.context.attach' });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.every(([url]) => url === '/context/attach')).toBe(true);
    const bodies = fetchMock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>);
    expect(bodies.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(bodies.every((body) => JSON.stringify(body.paths) === JSON.stringify(['folder with spaces/note.txt']))).toBe(true);
    expect(new Set(bodies.map((body) => body.interaction_id)).size).toBe(1);
    expect(bodies[2]).toMatchObject({ authorization_permit: 'context-permit' });
  });

  it('uses the shared authorization helper for credential provider configuration', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      const response = body.authorization_action === 'challenge'
        ? { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'provider-challenge' } } }
        : body.authorization_action === 'approve'
          ? { ok: true, authorization: { state: 'authorized', permit: { token: 'provider-permit' } } }
          : { ok: true, provider: 'openai', config: { has_secret: true } };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().configureProvider('openai', { api_key: 'transient-secret' }))
      .resolves.toMatchObject({ ok: true });
    const bodies = fetchMock.mock.calls.map((call) => JSON.parse(String((call[1] as RequestInit).body)) as Record<string, unknown>);
    expect(bodies.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(bodies[1]).toMatchObject({ challenge_id: 'provider-challenge', user_decision: 'approve' });
    expect(bodies[2]).toMatchObject({ authorization_permit: 'provider-permit' });
  });

  it('preserves project, file, plan, and provider operation payloads across their authorized lifecycle', async () => {
    const secret = 'transient-secret';
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      const response = body.authorization_action === 'challenge'
        ? { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-1' } } }
        : body.authorization_action === 'approve'
          ? { ok: true, authorization: { state: 'authorized', permit: { token: 'permit-1' } } }
          : { ok: true, state: 'done' };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    const logSpy = vi.spyOn(console, 'log');
    const storageSetItem = vi.fn();
    vi.stubGlobal('localStorage', { setItem: storageSetItem });
    vi.stubGlobal('fetch', fetchMock);
    const client = authorizedClient();

    await client.initProject('C:/work/project');
    await client.writeFile('src/example.ts', 'export const value = 1;');
    await client.executePlan('plan-1', { mode: 'safe' });
    await client.configureProvider('openai', { api_key: secret, model: 'gpt-test' });
    await client.configureProvider('openai', { clear_secret: true });

    const calls = fetchMock.mock.calls.map(([url, init]) => ({
      url,
      body: JSON.parse(String((init as RequestInit).body)) as Record<string, unknown>,
    }));
    for (let index = 0; index < calls.length; index += 3) {
      const lifecycle = calls.slice(index, index + 3).map((call) => call.body);
      expect(lifecycle.map((body) => body.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
      expect(new Set(lifecycle.map((body) => body.interaction_id)).size).toBe(1);
    }
    expect(calls[0]).toMatchObject({ url: '/project/init', body: { root: 'C:/work/project' } });
    expect(calls[3]).toMatchObject({ url: '/files/write', body: { path: 'src/example.ts', content: 'export const value = 1;' } });
    expect(calls[6]).toMatchObject({ url: '/plans/plan-1/execute', body: { mode: 'safe' } });
    expect(calls[9].body).toMatchObject({ provider: 'openai', api_key: secret, model: 'gpt-test' });
    expect(calls[12].body).toMatchObject({ provider: 'openai', clear_secret: true });
    expect(storageSetItem).not.toHaveBeenCalled();
    expect(logSpy).not.toHaveBeenCalled();
  });

  it('rejects malformed or rejected authorization challenges with safe backend details', async () => {
    const secret = 'transient-secret';
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false,
      state: 'blocked',
      error_code: 'authorization_denied',
      message: `Credential ${secret} was rejected`,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().configureProvider('openai', { api_key: secret }))
      .rejects.toMatchObject({
        name: 'BagoAuthorizationError',
        code: 'authorization_denied',
        message: expect.not.stringContaining(secret),
      });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(['blocked', 'failed', 'error'])('rejects %s execution states from an authorized request', async (state) => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>;
      const response = body.authorization_action === 'challenge'
        ? { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-terminal' } } }
        : body.authorization_action === 'approve'
          ? { ok: true, authorization: { state: 'authorized', permit: { token: 'permit-terminal' } } }
          : { ok: true, state, error_code: `execution_${state}`, message: `Execution ${state}` };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().executePlan('plan-1')).rejects.toMatchObject({
      name: 'BagoAuthorizationError',
      code: `execution_${state}`,
      message: `ejecutar el plan: Execution ${state}`,
    });
  });

  it('cancels after a challenge without approving or executing', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-cancelled' } }
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const client = createBagoClient('', '');
    client.setAuthorizationConfirmation(async () => false);

    await expect(client.executePlan('plan-1')).rejects.toMatchObject({
      name: 'BagoAuthorizationError',
      code: 'authorization_cancelled',
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body.authorization_action).toBe('challenge');
  });

  it('attempts the modern bootstrap only once before the legacy fallback', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const status = url === '/api/v1/ui/bootstrap' ? 404 : 200;
      return Promise.resolve(new Response(JSON.stringify({}), {
        status,
        headers: { 'Content-Type': 'application/json' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('', '').bootstrap();

    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/v1/ui/bootstrap')).toHaveLength(1);
  });

  it('applies a verified release through the dedicated endpoint', async () => {
    const response = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), {
      status,
      headers: { 'Content-Type': 'application/json' }
    });
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({ ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-1' } } }))
      .mockResolvedValueOnce(response({ ok: true, authorization: { state: 'authorized', permit: { token: 'permit-1' } } }))
      .mockResolvedValueOnce(response({ ok: true, status: 'applying', authorization: { state: 'consumed' } }, 202));
    vi.stubGlobal('fetch', fetchMock);

    await expect(authorizedClient().applyReleaseUpdate()).resolves.toMatchObject({ status: 'applying' });
    const calls = fetchMock.mock.calls.filter(([url]) => url === '/release/apply');
    expect(calls).toHaveLength(3);
    const payloads = calls.map(([, init]) => JSON.parse(String(init?.body)));
    expect(payloads.map((payload) => payload.authorization_action)).toEqual(['challenge', 'approve', 'execute']);
    expect(payloads[1]).toMatchObject({ challenge_id: 'challenge-1', user_decision: 'approve' });
    expect(payloads[2]).toMatchObject({ authorization_permit: 'permit-1' });
    expect(payloads[0].interaction_id).toBe(payloads[2].interaction_id);
  });

  it('creates a persistent empty conversation through the conversation contract', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      active_conversation_id: 'chat-new',
      conversations: [],
      history: { conversation_id: 'chat-new', messages: [], count: 0 }
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('', '').createConversation();

    expect(fetchMock).toHaveBeenCalledWith('/conversations', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ action: 'create', title: 'Nuevo chat' })
    }));
  });

  it('uses the canonical inspect and import package routes', async () => {
    const responses = [
      { ok: true },
      { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-1' } } },
      { ok: true, authorization: { state: 'authorized', permit: { token: 'permit-1' } } },
      { ok: true, package: { id: 'local.example' }, authorization: { state: 'consumed' } },
    ];
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(responses.shift()), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })));
    vi.stubGlobal('fetch', fetchMock);
    const client = authorizedClient();

    await client.inspectCapabilityPackage('example.bago.zip', 'YWJj');
    await client.importCapabilityPackage({ fileName: 'example.bago.zip', contentBase64: 'YWJj' });

    expect(fetchMock.mock.calls[0]).toEqual([
      '/api/v1/capability-packages/inspect',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"content_base64":"YWJj"')
      })
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      '/api/v1/capability-packages/import',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"authorization_action":"challenge"')
      })
    ]);
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ body: expect.stringContaining('"authorization_action":"approve"') }));
    expect(fetchMock.mock.calls[3][1]).toEqual(expect.objectContaining({ body: expect.stringContaining('"authorization_action":"execute"') }));
  });

  it('lists and installs bundled capability examples through canonical routes', async () => {
    const responses = [
      { ok: true, examples: [] },
      { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'example-challenge' } } },
      { ok: true, authorization: { state: 'authorized', permit: { token: 'example-permit' } } },
      { ok: true, package: { id: 'local.scheduled-report' }, authorization: { state: 'consumed' } },
    ];
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(responses.shift()), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })));
    vi.stubGlobal('fetch', fetchMock);
    const client = authorizedClient();

    await client.listCapabilityExamples();
    await client.installCapabilityExample('local.scheduled-report');

    expect(fetchMock.mock.calls[0]).toEqual([
      '/api/v1/capability-packages/examples',
      expect.objectContaining({ method: 'GET' })
    ]);
    expect(fetchMock.mock.calls[1]).toEqual([
      '/api/v1/capability-packages/local.scheduled-report/install-example',
      expect.objectContaining({ method: 'POST' })
    ]);
    expect(fetchMock.mock.calls[2][1]).toEqual(expect.objectContaining({ body: expect.stringContaining('"authorization_action":"approve"') }));
    expect(fetchMock.mock.calls[3][1]).toEqual(expect.objectContaining({ body: expect.stringContaining('"authorization_action":"execute"') }));
  });


  it('uses the real Simulation and RL laboratory endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })));
    vi.stubGlobal('fetch', fetchMock);
    const client = createBagoClient('', '');

    await client.setSimulationConfig({ enabled: true, mode: 'shadow' });
    await client.trainRlBc();
    await client.evalRlPolicy();

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/simulation/config',
      '/rl/train-bc',
      '/rl/eval'
    ]);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body))).toMatchObject({ enabled: true, mode: 'shadow' });
  });

});
